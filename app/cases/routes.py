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

router = APIRouter()

UPLOAD_DIR = "/tmp" 
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

class Case(BaseModel):
    id: str
    title: str
    status: str
    created_at: str

@router.get("/")
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
def create_case(payload: dict):
    driver = get_driver()
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    with driver.session() as session:
        session.run(
            "CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: $date})",
            id=case_id, title=payload.get("title"), date=str(datetime.datetime.now())
        )
    return {"id": case_id, "message": "Caso criado"}

@router.delete("/{case_id}")
def delete_case(case_id: str):
    driver = get_driver()
    with driver.session() as session:
        session.run("MATCH (c:Case {id: $id}) DETACH DELETE c", id=case_id)
    return {"status": "deleted"}

# --- LÓGICA DE UPLOAD V2 (COM NÓ DE DOCUMENTO) ---
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
        # Isso garante que você VEJA que o arquivo subiu
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
async def upload_evidence_no_slash(case_id: str, file: UploadFile = File(...)):
    return await process_upload_logic(case_id, file)

@router.post("/{case_id}/upload/")
async def upload_evidence_slash(case_id: str, file: UploadFile = File(...)):
    return await process_upload_logic(case_id, file)
