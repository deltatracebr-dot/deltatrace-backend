from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# --- ROTAS DE CASOS ---
app.include_router(cases_routes.router, prefix="/cases", tags=["Cases"])

@app.on_event("startup")
def startup_event():
    verify_connection()

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "1.5 - GraphFix"}

# --- ROTA DE GRAFOS (Movida para cá para evitar 404) ---
@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    print(f"--> Buscando grafo para o caso: {case_id}")
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            # 1. Tenta buscar o caso e suas conexões diretas
            result = session.run("""
                MATCH (c:Case {id: $case_id})-[r]-(n)
                RETURN c, r, n
            """, case_id=case_id)
            
            # Se não tiver conexões, busca só o nó do caso para não dar erro
            has_records = False
            
            for record in result:
                has_records = True
                # Processa o Nó Conectado (n)
                node = record["n"]
                node_id = node.element_id if hasattr(node, "element_id") else str(node.id)
                labels = list(node.labels)
                label_display = labels[0] if labels else "Node"
                
                # Nome do nó (tenta pegar name, title ou label)
                props = dict(node.items())
                name = props.get("label") or props.get("name") or props.get("title") or "Sem Nome"
                
                # Adiciona Nó
                nodes.append({
                    "id": node_id,
                    "type": "default", 
                    "data": { "label": f"{label_display}\n{name}" },
                    "position": { "x": 0, "y": 0 }
                })
                
                # Processa a Relação (r)
                rel = record["r"]
                # O nó de origem da relação pode ser o Caso ou o Nó
                start = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(rel.start_node.id)
                end = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(rel.end_node.id)
                
                edges.append({
                    "id": f"e{start}-{end}",
                    "source": start,
                    "target": end,
                    "animated": True,
                    "style": { "stroke": "#10b981", "strokeWidth": 2 }
                })

            # Se não achou nada conectado, adiciona pelo menos o nó central do Caso
            if not has_records:
                print("Nenhuma conexão encontrada, buscando nó raiz...")
                root_result = session.run("MATCH (c:Case {id: $case_id}) RETURN c", case_id=case_id)
                record = root_result.single()
                if record:
                    c = record["c"]
                    cid = c.element_id if hasattr(c, "element_id") else str(c.id)
                    title = c.get("title", "Caso Sem Nome")
                    nodes.append({
                        "id": cid,
                        "type": "input",
                        "data": { "label": f"📂 CASO\n{title}" },
                        "position": { "x": 0, "y": 0 }
                    })

    except Exception as e:
        print(f"Erro ao gerar grafo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"nodes": nodes, "edges": edges}

# --- ROTA DUPLA DE GRAFOS (Para o Proxy) ---
@app.get("/api/graph/case/{case_id}")
def get_case_graph_api(case_id: str):
    return get_case_graph(case_id)

# --- LÓGICA DE PROCESSAMENTO DE PDF ---
async def process_pdf_logic(target_name: str, file: UploadFile):
    print(f"--> Recebendo arquivo: {file.filename} para alvo: {target_name}")
    text_content = ""
    try:
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: text_content += text + "\n"
    except Exception as e:
        print(f"Erro PDF: {e}")

    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    relevant_phones = [p for p in phones if p.confidence_score > 30]

    return {
        "target": {
            "name": target_name,
            "cpf": "PENDING",
            "surnames": extractor.target_surnames,
            "raw_text": "Processado",
            "source_pdf": file.filename
        },
        "phones": relevant_phones,
        "addresses": addresses
    }

@app.post("/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_root(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)

@app.post("/api/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_api(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)
