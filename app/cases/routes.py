from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List
import uuid
import shutil
import os
import datetime
import pdfplumber
from app.database import get_driver
from app.services.extractor import Mind7Extractor
from pydantic import BaseModel

# ========== CONFIGURAÇÃO DO ROUTER ==========
# prefix="/cases" AQUI + redirect_slashes=False para evitar 307
router = APIRouter(prefix="/cases", redirect_slashes=False)

UPLOAD_DIR = "/tmp" 
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

class Case(BaseModel):
    id: str
    title: str
    status: str
    created_at: str

# ========== ROTAS BÁSICAS (com e sem barra) ==========

@router.get("/")
@router.get("")
def list_cases():
    driver = get_driver()
    cases = []
    if not driver: return []
    with driver.session() as session:
        result = session.run("MATCH (c:Case) RETURN c ORDER BY c.created_at DESC")
        for record in result:
            node = record["c"]
            cases.append({
                "id": node.get("id"),
                "title": node.get("title"),
                "status": node.get("status", "Em andamento"),
                "created_at": node.get("created_at", "")
            })
    return cases

@router.post("/")
@router.post("")
def create_case(payload: dict):
    driver = get_driver()
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    with driver.session() as session:
        session.run(
            "CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: $date})",
            id=case_id, title=payload.get("title"), date=str(datetime.datetime.now())
        )
    return {"id": case_id, "message": "Caso criado"}

# ========== LÓGICA DE UPLOAD (mantida igual) ==========

async def process_upload_logic(case_id: str, file: UploadFile):
    driver = get_driver()
    print(f"--> Processando Upload: {file.filename}")
    
    file_path = f"{UPLOAD_DIR}/{case_id}_{file.filename}"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except:
        return {"status": "error", "detail": "Falha IO"}
    
    text_content = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: text_content += text + "\n"
    except Exception as e:
        print(f"Erro PDF: {e}")
    
    target_name = "ALVO"
    with driver.session() as session:
        res = session.run("MATCH (c:Case {id: $id}) RETURN c.title as title", id=case_id).single()
        if res: target_name = res["title"]

    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    
    count = 0
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    
    with driver.session() as session:
        # 1. CRIAR NÓ DO DOCUMENTO (EVIDÊNCIA)
        session.run("""
            MATCH (c:Case {id: $cid})
            MERGE (d:Document {id: $doc_id})
            ON CREATE SET d.label = $filename, d.type = 'evidence', d.created_at = $date
            MERGE (c)-[:CONTAINS_EVIDENCE]->(d)
        """, cid=case_id, doc_id=doc_id, filename=file.filename, date=str(datetime.datetime.now()))

        # 2. Ligar Telefones ao Documento E ao Alvo
        for p in phones:
            if p.confidence_score > 30:
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    MATCH (c:Case {id: $cid})
                    MERGE (p:Person {name: $name})
                    MERGE (c)-[:INVESTIGATES]->(p)
                    
                    MERGE (t:Phone {label: $num})
                    ON CREATE SET t.type = 'phone', t.owner = $owner
                    
                    MERGE (d)-[:SOURCE_OF]->(t)
                    MERGE (p)-[:HAS_PHONE]->(t)
                """, doc_id=doc_id, cid=case_id, name=target_name, num=p.number, owner=p.registered_owner)
                count += 1
        
        # 3. Ligar Endereços ao Documento E ao Alvo
        for a in addresses:
            session.run("""
                MATCH (d:Document {id: $doc_id})
                MATCH (c:Case {id: $cid})
                MERGE (p:Person {name: $name})
                
                MERGE (addr:Address {label: $full})
                ON CREATE SET addr.type = 'address'
                
                MERGE (d)-[:SOURCE_OF]->(addr)
                MERGE (p)-[:LIVES_AT]->(addr)
            """, doc_id=doc_id, cid=case_id, name=target_name, full=a.full_address)
            count += 1

    try: os.remove(file_path)
    except: pass

    return {"status": "processed", "count": count, "detail": f"Evidência processada."}

@router.post("/{case_id}/upload")
@router.post("/{case_id}/upload/")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    return await process_upload_logic(case_id, file)

# ========== ROTA DE LIMPEZA ==========

@router.post("/{case_id}/clean")
@router.post("/{case_id}/clean/")
def clean_case_data(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco desconectado")
        
    deleted_count = 0
    with driver.session() as session:
        q1 = session.run("""
            MATCH (n:Phone)
            WHERE n.label CONTAINS '000000' 
               OR size(n.label) < 8 
               OR n.label CONTAINS 'N/I'
            DETACH DELETE n
            RETURN count(n) as c
        """)
        deleted_count += q1.single()["c"]

        q2 = session.run("""
            MATCH (n:Address)
            WHERE size(n.label) < 5 
               OR n.label CONTAINS 'N/I' 
               OR n.label = 'ENDEREÇO'
            DETACH DELETE n
            RETURN count(n) as c
        """)
        deleted_count += q2.single()["c"]
        
        q3 = session.run("""
            MATCH (n)
            WHERE n.label IN ['DADO S/N', 'DADO BRUTO', 'Unknown', 'N/A']
            DETACH DELETE n
            RETURN count(n) as c
        """)
        deleted_count += q3.single()["c"]

    return {"status": "cleaned", "deleted_nodes": deleted_count, "message": f"Limpeza concluída. {deleted_count} nós removidos."}

# ========== ROTAS PARA OS TRÊS PONTINHOS ==========

@router.delete("/{case_id}")
@router.delete("/{case_id}/")
def delete_case(case_id: str):
    """Exclui um caso (para botão Excluir)"""
    driver = get_driver()
    with driver.session() as session:
        session.run("MATCH (c:Case {id: $id}) DETACH DELETE c", id=case_id)
    return {"status": "deleted"}

@router.get("/{case_id}/export")
@router.get("/{case_id}/export/")
def export_case(case_id: str):
    """Exporta caso para JSON (para botão Backup/Exportar)"""
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco desconectado")
    
    with driver.session() as session:
        result = session.run("MATCH (c:Case {id: $id}) RETURN c", id=case_id).single()
        if not result:
            raise HTTPException(status_code=404, detail="Caso não encontrado")
        
        case_data = dict(result["c"])
        return {
            "status": "success",
            "case": case_data,
            "exported_at": datetime.datetime.now().isoformat(),
            "message": "Caso exportado com sucesso"
        }

@router.get("/{case_id}/info")
@router.get("/{case_id}/info/")
def get_case_info(case_id: str):
    """Informações detalhadas do caso (para botão Detalhes)"""
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco desconectado")
    
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Case {id: $id})
            OPTIONAL MATCH (c)-[:REQUESTED_BY]->(solicitante:Person)
            OPTIONAL MATCH (c)-[:TARGET]->(investigado:Person)
            RETURN c, solicitante, investigado
        """, id=case_id).single()
        
        if not result or not result["c"]:
            raise HTTPException(status_code=404, detail="Caso não encontrado")
        
        # Contar documentos e evidências
        stats = session.run("""
            MATCH (c:Case {id: $id})
            OPTIONAL MATCH (c)-[:CONTAINS_EVIDENCE]->(doc:Document)
            OPTIONAL MATCH (doc)-[:SOURCE_OF]->(evidence)
            RETURN 
                count(DISTINCT doc) as documentos,
                count(DISTINCT evidence) as evidencias
        """, id=case_id).single()
        
        return {
            "case": dict(result["c"]),
            "solicitante": dict(result["solicitante"]) if result["solicitante"] else None,
            "investigado": dict(result["investigado"]) if result["investigado"] else None,
            "estatisticas": {
                "documentos": stats["documentos"] if stats else 0,
                "evidencias": stats["evidencias"] if stats else 0
            },
            "urls": {
                "export": f"/cases/{case_id}/export",
                "graph": f"/graph?case_id={case_id}"
            }
        }

@router.get("/{case_id}/actions")
@router.get("/{case_id}/actions/")
def get_case_actions(case_id: str):
    """Retorna todas ações disponíveis para um caso (para menu três pontinhos)"""
    return {
        "actions": [
            {
                "name": "export",
                "method": "GET",
                "url": f"/cases/{case_id}/export",
                "label": "📥 Exportar Caso",
                "description": "Exporta todos os dados do caso para JSON"
            },
            {
                "name": "delete",
                "method": "DELETE",
                "url": f"/cases/{case_id}",
                "label": "🗑️ Excluir Caso",
                "description": "Remove permanentemente o caso e todos os dados relacionados",
                "danger": True
            },
            {
                "name": "info",
                "method": "GET",
                "url": f"/cases/{case_id}/info",
                "label": "📊 Ver Detalhes",
                "description": "Visualizar informações detalhadas do caso"
            },
            {
                "name": "clean",
                "method": "POST",
                "url": f"/cases/{case_id}/clean",
                "label": "🧹 Limpar Dados",
                "description": "Remover dados inválidos ou duplicados"
            },
            {
                "name": "upload",
                "method": "POST",
                "url": f"/cases/{case_id}/upload",
                "label": "📎 Anexar Evidência",
                "description": "Enviar documento PDF para análise"
            }
        ],
        "case_id": case_id,
        "timestamp": datetime.datetime.now().isoformat()
    }