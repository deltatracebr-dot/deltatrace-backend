from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber

# Imports do Sistema DeltaTrace
from app.cases import intake_routes
from app.cases import routes as cases_routes
from app.services.report_generator import generate_pdf_report
from app.services.extractor import Mind7Extractor
from app.database import verify_connection, get_driver

# Imports Essenciais para Validar o Contrato (MIND-7)
from app.schemas import InvestigationReport, PersonResult, PhoneResult, AddressResult

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas
app.include_router(cases_routes.router, tags=["Cases"])
app.include_router(intake_routes.router)

@app.on_event("startup")
def startup_event():
    verify_connection()

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "2.4 - Architect Fix"}

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
                
                for node in path.nodes:
                    nid = node.element_id if hasattr(node, "element_id") else str(node.id)
                    
                    if nid not in seen_nodes:
                        seen_nodes.add(nid)
                        labels = list(node.labels)
                        props = dict(node.items())
                        
                        label = props.get("label") or props.get("name") or props.get("number") or props.get("full_address") or props.get("title")
                        
                        if not label or label in ["DADO", "DADO S/N", "null"]:
                            continue 

                        ntype = "default"
                        if "Person" in labels: ntype = "person"
                        elif "Phone" in labels: ntype = "phone"
                        elif "Address" in labels: ntype = "address"
                        elif "Case" in labels: ntype = "case"
                        elif "Document" in labels: ntype = "case"

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

# --- LÓGICA DE PROCESSAMENTO DE PDF (CORRIGIDA E ROBUSTA) ---
async def process_pdf_logic(target_name: str, file: UploadFile) -> InvestigationReport:
    print(f"--> [MIND-7] Iniciando análise para: {target_name}")
    text_content = ""
    
    # 1. Extração de Texto (Segura)
    try:
        # Reposiciona ponteiro do arquivo se necessário
        await file.seek(0)
        # Lê os bytes para o pdfplumber
        file_bytes = await file.read()
        
        # Uso do pdfplumber com bytes (workaround usando BytesIO se necessário, mas tentando direto)
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text_content += t + "\n"
    except Exception as e:
        print(f"--> [ERRO LEITURA PDF] {e}")
        text_content = "Erro ao ler conteúdo do PDF."

    # 2. Inteligência (Extractor)
    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    
    # Filtro de Confiança
    relevant_phones = [p for p in phones if p.confidence_score > 30]

    # 3. CONSTRUÇÃO DO CONTRATO RIGOROSO (A CORREÇÃO PRINCIPAL)
    # Precisamos criar objetos Pydantic explicitamente para evitar erros de validação
    
    target_obj = PersonResult(
        raw_text=text_content[:2000], # Limita tamanho para não estourar payload se for gigante
        source_pdf=file.filename or "upload.pdf",
        name=target_name.upper(),
        cpf="Não identificado", # Default seguro
        surnames=[]
    )

    report = InvestigationReport(
        target=target_obj,
        phones=relevant_phones,
        addresses=addresses
    )
    
    print("--> [MIND-7] Relatório gerado com sucesso.")
    return report

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