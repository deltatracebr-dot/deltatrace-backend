from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber
from app.services.extractor import Mind7Extractor
from app.schemas import InvestigationReport
from app.cases import routes as cases_routes
from app.database import verify_connection, get_driver

app = FastAPI()

# --- CONFIGURAÇÃO DE SEGURANÇA (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROTAS DE CASOS ---
app.include_router(cases_routes.router, prefix="/cases", tags=["Cases"])

@app.on_event("startup")
def startup_event():
    verify_connection()

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "2.0 - Stable"}

# --- SCHEMA DE NOTAS ---
class NoteUpdate(BaseModel):
    note: str

# --- ROTA DE GRAFO (CORRIGIDA E DEFINITIVA) ---
@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            # Busca tudo conectado ao caso
            result = session.run("""
                MATCH (c:Case {id: $case_id})-[r]-(n)
                RETURN c, r, n
            """, case_id=case_id)
            
            seen_nodes = set()
            has_records = False
            
            for record in result:
                has_records = True
                
                # --- PROCESSAMENTO DO NÓ ---
                node = record["n"]
                node_id = node.element_id if hasattr(node, "element_id") else str(node.id)
                
                if node_id in seen_nodes: continue
                seen_nodes.add(node_id)

                labels = list(node.labels)
                props = dict(node.items())
                
                # LÓGICA DE EXIBIÇÃO (PRIORIDADE PARA O VALOR REAL)
                # Tenta encontrar o valor em várias propriedades comuns
                real_value = props.get("label") or props.get("number") or props.get("full_address") or props.get("name") or props.get("title") or "DADO S/N"
                
                # Determinar Tipo para Cor
                node_type = "default"
                if "Person" in labels: 
                    node_type = "person"
                    # Se for pessoa, garante que o nome aparece
                    if props.get("name"): real_value = props.get("name")
                elif "Phone" in labels: 
                    node_type = "phone"
                elif "Address" in labels: 
                    node_type = "address"
                elif "Case" in labels: 
                    node_type = "case"
                    real_value = f"CASO: {props.get('title', 'S/N')}"

                # Monta o nó para o Frontend
                nodes.append({
                    "id": node_id,
                    "type": "default", 
                    "data": { 
                        "label": real_value, # <--- AQUI ESTAVA O PROBLEMA, AGORA VAI O VALOR CERTO
                        "type": node_type,
                        "full_data": props,
                        "note": props.get("note", "")
                    },
                    "position": { "x": 0, "y": 0 }
                })
                
                # --- PROCESSAMENTO DA LINHA (EDGE) ---
                rel = record["r"]
                start = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(rel.start_node.id)
                end = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(rel.end_node.id)
                
                edges.append({
                    "id": f"e{start}-{end}",
                    "source": start,
                    "target": end,
                    "animated": True,
                    "style": { "stroke": "#00FF85", "strokeWidth": 1.5, "strokeDasharray": "5 5" }
                })

            # Se não tiver conexões, mostra pelo menos o Caso
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

# Rota Dupla para Proxy
@app.get("/api/graph/case/{case_id}")
def get_case_graph_api(case_id: str):
    return get_case_graph(case_id)

# --- ROTA DE SALVAR NOTAS ---
@app.post("/graph/node/{node_id}/note")
def update_node_note(node_id: str, payload: NoteUpdate):
    driver = get_driver()
    with driver.session() as session:
        session.run("""
            MATCH (n) WHERE elementId(n) = $id OR id(n) = toInteger($id)
            SET n.note = $note
        """, id=node_id, note=payload.note)
    return {"status": "success"}

@app.post("/api/graph/node/{node_id}/note")
def update_node_note_api(node_id: str, payload: NoteUpdate):
    return update_node_note(node_id, payload)

# --- MESA DE ANÁLISE (PDF) ---
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
    # Filtro de relevância
    relevant_phones = [p for p in phones if p.confidence_score > 30]

    return {
        "target": {"name": target_name, "cpf": "PENDING", "surnames": extractor.target_surnames, "raw_text": "OK", "source_pdf": file.filename},
        "phones": relevant_phones,
        "addresses": addresses
    }

@app.post("/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_root(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)

@app.post("/api/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_api(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)
