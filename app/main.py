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

app.include_router(cases_routes.router, prefix="/cases", tags=["Cases"])

@app.on_event("startup")
def startup_event():
    verify_connection()

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "1.6 - Visual Upgrade"}

# --- INTELLIGENCE GRAPH ENGINE ---
@app.get("/graph/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    try:
        with driver.session() as session:
            # Busca nós conectados ao caso
            result = session.run("""
                MATCH (c:Case {id: $case_id})-[r]-(n)
                RETURN c, r, n
            """, case_id=case_id)
            
            seen_nodes = set()
            
            for record in result:
                # 1. Processar Nó (Alvo/Telefone/Endereço)
                node = record["n"]
                node_id = node.element_id if hasattr(node, "element_id") else str(node.id)
                
                if node_id in seen_nodes: continue
                seen_nodes.add(node_id)

                labels = list(node.labels)
                main_label = labels[0] if labels else "Unknown"
                props = dict(node.items())
                
                # Definição de Ícones e Estilos baseados no Tipo
                display_label = "❓ Desconhecido"
                node_type = "default"
                
                # Lógica de Formatação Visual
                if "Person" in labels:
                    display_label = f"👤 {props.get('name', 'Alvo')}"
                    node_type = "person"
                elif "Phone" in labels:
                    display_label = f"📱 {props.get('label', props.get('number', 'Tel'))}"
                    node_type = "phone"
                elif "Address" in labels:
                    addr = props.get('label', props.get('full_address', 'Endereço'))
                    # Quebra endereço grande
                    if len(addr) > 20: addr = addr[:20] + "..."
                    display_label = f"📍 {addr}"
                    node_type = "address"
                elif "Case" in labels:
                    display_label = f"📂 CASO: {props.get('title', 'Inv')}"
                    node_type = "case"

                nodes.append({
                    "id": node_id,
                    "type": "default", # ReactFlow usa default, estilizamos no style
                    "data": { 
                        "label": display_label,
                        "type": node_type, # Para o frontend saber a cor
                        "full_data": props 
                    },
                    "position": { "x": 0, "y": 0 }
                })
                
                # 2. Processar Caso (Nó Central)
                case_node = record["c"]
                c_id = case_node.element_id if hasattr(case_node, "element_id") else str(case_node.id)
                if c_id not in seen_nodes:
                    seen_nodes.add(c_id)
                    nodes.append({
                        "id": c_id,
                        "data": { "label": f"📂 {case_node.get('title')}", "type": "case" },
                        "position": { "x": 0, "y": 0 }
                    })

                # 3. Processar Aresta (Linha)
                rel = record["r"]
                start = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(rel.start_node.id)
                end = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(rel.end_node.id)
                
                edges.append({
                    "id": f"e{start}-{end}",
                    "source": start,
                    "target": end,
                    "animated": True,
                    "style": { "stroke": "#334155", "strokeWidth": 2 }
                })

    except Exception as e:
        print(f"Erro grafo: {e}")
        return {"nodes": [], "edges": []}

    return {"nodes": nodes, "edges": edges}

@app.get("/api/graph/case/{case_id}")
def get_case_graph_api(case_id: str):
    return get_case_graph(case_id)

# --- OUTRAS ROTAS (Mantendo Upload e Extrator) ---
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
