from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # <--- Importante
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
    return {"status": "DeltaTrace Intelligence Online", "version": "1.7 - Notes Enabled"}

# --- SCHEMA PARA NOTAS ---
class NoteUpdate(BaseModel):
    note: str

# --- ROTA DE GRAFOS (LEITURA) ---
@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (c:Case {id: $case_id})-[r]-(n)
                RETURN c, r, n
            """, case_id=case_id)
            
            seen_nodes = set()
            has_records = False
            
            for record in result:
                has_records = True
                node = record["n"]
                node_id = node.element_id if hasattr(node, "element_id") else str(node.id)
                
                if node_id in seen_nodes: continue
                seen_nodes.add(node_id)

                labels = list(node.labels)
                main_label = labels[0] if labels else "Unknown"
                props = dict(node.items())
                name = props.get("label") or props.get("name") or props.get("title") or "Sem Nome"
                
                nodes.append({
                    "id": node_id,
                    "type": "default", 
                    "data": { 
                        "label": f"{main_label}\n{name}", 
                        "type": "default", # Simplificado, o front trata
                        "full_data": props,
                        "note": props.get("note", "") # <--- Carrega a nota existente
                    },
                    "position": { "x": 0, "y": 0 }
                })
                
                rel = record["r"]
                start = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(rel.start_node.id)
                end = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(rel.end_node.id)
                
                edges.append({
                    "id": f"e{start}-{end}",
                    "source": start,
                    "target": end,
                    "animated": True,
                    "style": { "stroke": "#00FF85", "strokeWidth": 2 }
                })

            if not has_records:
                root_result = session.run("MATCH (c:Case {id: $case_id}) RETURN c", case_id=case_id)
                record = root_result.single()
                if record:
                    c = record["c"]
                    cid = c.element_id if hasattr(c, "element_id") else str(c.id)
                    title = c.get("title", "Caso Sem Nome")
                    nodes.append({
                        "id": cid,
                        "type": "input",
                        "data": { "label": f"📂 CASO\n{title}", "type": "case" },
                        "position": { "x": 0, "y": 0 }
                    })

    except Exception as e:
        print(f"Erro grafo: {e}")
        return {"nodes": [], "edges": []}

    return {"nodes": nodes, "edges": edges}

@app.get("/api/graph/case/{case_id}")
def get_case_graph_api(case_id: str):
    return get_case_graph(case_id)

# --- ROTA DE SALVAR NOTAS (NOVA) ---
@app.post("/graph/node/{node_id}/note")
def update_node_note(node_id: str, payload: NoteUpdate):
    print(f"Salvando nota no nó {node_id}: {payload.note}")
    driver = get_driver()
    with driver.session() as session:
        # Tenta pelo ID novo (elementId) ou ID antigo (integer)
        session.run("""
            MATCH (n) 
            WHERE elementId(n) = $id OR id(n) = toInteger($id)
            SET n.note = $note
        """, id=node_id, note=payload.note)
    return {"status": "success"}

@app.post("/api/graph/node/{node_id}/note")
def update_node_note_api(node_id: str, payload: NoteUpdate):
    return update_node_note(node_id, payload)

# --- ROTAS DE PDF ---
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
