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
    return {"status": "DeltaTrace Intelligence Online", "version": "1.9 - Edge Fix"}

class NoteUpdate(BaseModel):
    note: str

@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            # QUERY MELHORADA: Retorna IDs explícitos das arestas
            result = session.run("""
                MATCH (c:Case {id: $case_id})-[r]-(n)
                RETURN c, n, r, elementId(c) as source_id, elementId(n) as target_id
            """, case_id=case_id)
            
            seen_nodes = set()
            has_records = False
            
            for record in result:
                has_records = True
                
                # 1. Nó (Target)
                node = record["n"]
                node_id = record["target_id"] # ID direto do banco
                
                if node_id not in seen_nodes:
                    seen_nodes.add(node_id)
                    labels = list(node.labels)
                    props = dict(node.items())
                    
                    real_value = props.get("label") or props.get("number") or props.get("full_address") or props.get("name") or props.get("title") or "DADO S/N"
                    
                    node_type = "default"
                    if "Person" in labels: 
                        node_type = "person"
                        if props.get("name"): real_value = props.get("name")
                    elif "Phone" in labels: node_type = "phone"
                    elif "Address" in labels: node_type = "address"
                    
                    nodes.append({
                        "id": node_id,
                        "type": "default", 
                        "data": { 
                            "label": real_value, 
                            "type": node_type,
                            "full_data": props,
                            "note": props.get("note", "")
                        },
                        "position": { "x": 0, "y": 0 }
                    })
                
                # 2. Nó Central (Case)
                case_node = record["c"]
                case_id_db = record["source_id"] # ID direto do banco
                
                if case_id_db not in seen_nodes:
                    seen_nodes.add(case_id_db)
                    nodes.append({
                        "id": case_id_db,
                        "data": { "label": f"CASO: {case_node.get('title')}", "type": "case" },
                        "position": { "x": 0, "y": 0 }
                    })

                # 3. Aresta (Edge)
                # IMPORTANTE: Usamos os IDs capturados na query para garantir o match
                edges.append({
                    "id": f"e{case_id_db}-{node_id}",
                    "source": case_id_db,
                    "target": node_id,
                    "animated": True,
                    "style": { "stroke": "#00FF85", "strokeWidth": 2 }
                })

            if not has_records:
                root = session.run("MATCH (c:Case {id: $case_id}) RETURN c, elementId(c) as id", case_id=case_id).single()
                if root:
                    cid = root["id"]
                    c = root["c"]
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
        session.run("""
            MATCH (n) WHERE elementId(n) = $id OR id(n) = toInteger($id)
            SET n.note = $note
        """, id=node_id, note=payload.note)
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
