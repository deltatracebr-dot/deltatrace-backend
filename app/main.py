from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber
from app.services.extractor import Mind7Extractor
from app.schemas import InvestigationReport
from app.cases import routes as cases_routes
from app.database import verify_connection, get_driver

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_routes.router, prefix="/cases", tags=["Cases"])

@app.on_event("startup")
def startup_event():
    verify_connection()

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "2.2 - Deep Graph"}

class NoteUpdate(BaseModel):
    note: str

# --- ENGINE DO GRAFO (AGORA COM VISÃO PROFUNDA) ---
@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            # QUERY NIVEL 2: Busca o Caso -> Vizinhos -> Vizinhos dos Vizinhos
            result = session.run("""
                MATCH (c:Case {id: $case_id})
                OPTIONAL MATCH (c)-[r1]-(n)
                OPTIONAL MATCH (n)-[r2]-(m)
                RETURN c, r1, n, r2, m
            """, case_id=case_id)
            
            seen_nodes = set()
            seen_edges = set()
            
            for record in result:
                # 1. Nó Central (Caso)
                if record["c"]:
                    c = record["c"]
                    cid = c.element_id if hasattr(c, "element_id") else str(c.id)
                    if cid not in seen_nodes:
                        seen_nodes.add(cid)
                        nodes.append({
                            "id": cid,
                            "type": "default",
                            "data": { "label": f"CASO: {c.get('title', 'S/N')}", "type": "case", "full_data": dict(c.items()) },
                            "position": { "x": 0, "y": 0 }
                        })

                # 2. Nível 1 (Vizinhos diretos: Documentos, Pessoas ligadas ao caso)
                if record["n"]:
                    process_node(record["n"], nodes, seen_nodes)
                    if record["r1"]:
                        process_edge(record["r1"], edges, seen_edges, record["c"], record["n"])

                # 3. Nível 2 (Vizinhos dos vizinhos: Telefones dentro dos Documentos)
                if record["m"]:
                    process_node(record["m"], nodes, seen_nodes)
                    if record["r2"]:
                        process_edge(record["r2"], edges, seen_edges, record["n"], record["m"])

    except Exception as e:
        print(f"Erro grafo: {e}")
        return {"nodes": [], "edges": []}

    return {"nodes": nodes, "edges": edges}

# --- FUNÇÕES AUXILIARES PARA LIMPAR O CÓDIGO ---
def process_node(node_obj, nodes_list, seen_set):
    nid = node_obj.element_id if hasattr(node_obj, "element_id") else str(node_obj.id)
    if nid in seen_set: return
    seen_set.add(nid)
    
    labels = list(node_obj.labels)
    props = dict(node_obj.items())
    
    # Determinar Label
    label = props.get("label") or props.get("name") or props.get("number") or props.get("full_address") or props.get("title") or "DADO"
    
    # Determinar Tipo (Cor)
    ntype = "default"
    if "Person" in labels: ntype = "person"
    elif "Phone" in labels: ntype = "phone"
    elif "Address" in labels: ntype = "address"
    elif "Document" in labels: ntype = "document" # Novo tipo para ficar azul escuro/roxo
    elif "Case" in labels: ntype = "case"

    nodes_list.append({
        "id": nid,
        "type": "default",
        "data": { "label": label, "type": ntype, "full_data": props, "note": props.get("note", "") },
        "position": { "x": 0, "y": 0 }
    })

def process_edge(rel_obj, edges_list, seen_set, start_node, end_node):
    # Identificar IDs de origem/destino da relação
    # O driver Neo4j nem sempre retorna start/end na ordem visual, então usamos os IDs dos nós passados
    sid = start_node.element_id if hasattr(start_node, "element_id") else str(start_node.id)
    eid = end_node.element_id if hasattr(end_node, "element_id") else str(end_node.id)
    
    # A relação precisa conectar os dois nós que estamos processando
    rid = rel_obj.element_id if hasattr(rel_obj, "element_id") else str(rel_obj.id)
    
    if rid in seen_set: return
    seen_set.add(rid)

    edges_list.append({
        "id": f"e_{rid}",
        "source": sid,
        "target": eid,
        "animated": True,
        "style": { "stroke": "#00FF85", "strokeWidth": 1.5, "strokeDasharray": "5 5" }
    })

@app.get("/api/graph/case/{case_id}")
def get_case_graph_api(case_id: str):
    return get_case_graph(case_id)

@app.post("/graph/node/{node_id}/note")
def update_node_note(node_id: str, payload: NoteUpdate):
    driver = get_driver()
    with driver.session() as session:
        session.run("MATCH (n) WHERE elementId(n) = $id OR id(n) = toInteger($id) SET n.note = $note", id=node_id, note=payload.note)
    return {"status": "success"}

@app.post("/api/graph/node/{node_id}/note")
def update_node_note_api(node_id: str, payload: NoteUpdate):
    return update_node_note(node_id, payload)

async def process_pdf_logic(target_name: str, file: UploadFile):
    text_content = ""
    try:
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text_content += t + "\n"
    except: pass
    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    relevant_phones = [p for p in phones if p.confidence_score > 30]
    return {"target": {"name": target_name}, "phones": relevant_phones, "addresses": addresses}

@app.post("/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_root(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)

@app.post("/api/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_api(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)
