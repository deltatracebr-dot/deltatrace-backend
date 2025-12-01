from fastapi.responses import StreamingResponse
from app.services.report_generator import generate_pdf_report
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
    return {"status": "DeltaTrace Intelligence Online", "version": "2.3 - PathFix"}

class NoteUpdate(BaseModel):
    note: str

# --- ENGINE DO GRAFO (MODO PATHFINDING) ---
@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            # QUERY DE CAMINHO: Busca tudo que está conectado em até 2 saltos
            # Isso GARANTE que as linhas venham junto com os nós
            result = session.run("""
                MATCH path = (c:Case {id: $case_id})-[*1..2]-(n)
                RETURN path
            """, case_id=case_id)
            
            seen_nodes = set()
            seen_edges = set()
            has_records = False
            
            for record in result:
                has_records = True
                path = record["path"]
                
                # 1. Processar Nós do Caminho
                for node in path.nodes:
                    nid = node.element_id if hasattr(node, "element_id") else str(node.id)
                    
                    if nid not in seen_nodes:
                        seen_nodes.add(nid)
                        labels = list(node.labels)
                        props = dict(node.items())
                        
                        # Definição de Label (Prioridade de Dados)
                        label = props.get("label") or props.get("name") or props.get("number") or props.get("full_address") or props.get("title")
                        
                        # Filtro Anti-Lixo (Remove nós sem label útil)
                        if not label or label in ["DADO", "DADO S/N", "null"]:
                            continue 

                        # Definição de Tipo
                        ntype = "default"
                        if "Person" in labels: ntype = "person"
                        elif "Phone" in labels: ntype = "phone"
                        elif "Address" in labels: ntype = "address"
                        elif "Case" in labels: ntype = "case"
                        elif "Document" in labels: ntype = "case" # Documento usa estilo de case por enquanto

                        nodes.append({
                            "id": nid,
                            "type": "default",
                            "data": { 
                                "label": label, 
                                "type": ntype, 
                                "full_data": props, 
                                "note": props.get("note", "") 
                            },
                            "position": { "x": 0, "y": 0 }
                        })

                # 2. Processar Linhas (Arestas) do Caminho
                for rel in path.relationships:
                    rid = rel.element_id if hasattr(rel, "element_id") else str(rel.id)
                    
                    if rid not in seen_edges:
                        seen_edges.add(rid)
                        start = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(rel.start_node.id)
                        end = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(rel.end_node.id)
                        
                        edges.append({
                            "id": f"e_{rid}",
                            "source": start,
                            "target": end,
                            "animated": True,
                            "style": { "stroke": "#00FF85", "strokeWidth": 2, "strokeDasharray": "5 5" }
                        })

            # Fallback: Se não tiver conexões, mostra o nó central do Caso
            if not has_records:
                root = session.run("MATCH (c:Case {id: $case_id}) RETURN c", case_id=case_id).single()
                if root:
                    c = root["c"]
                    cid = c.element_id if hasattr(c, "element_id") else str(c.id)
                    nodes.append({
                        "id": cid,
                        "type": "input",
                        "data": { "label": c.get("title", "Caso"), "type": "case" },
                        "position": { "x": 0, "y": 0 }
                    })

    except Exception as e:
        print(f"Erro grafo: {e}")
        return {"nodes": [], "edges": []}

    return {"nodes": nodes, "edges": edges}

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

# --- ROTA DE RELATÓRIO PDF ---
@app.get("/report/{case_id}")
def download_case_report(case_id: str):
    pdf_buffer = generate_pdf_report(case_id)
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=Dossie_{case_id}.pdf"}
    )

@app.get("/api/report/{case_id}")
def download_case_report_api(case_id: str):
    return download_case_report(case_id)
