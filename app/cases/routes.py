from fastapi import APIRouter, UploadFile, File, HTTPException
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

# --- DIRETÓRIO TEMPORÁRIO ---
UPLOAD_DIR = "/tmp" # Melhor para ambientes cloud como Render
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- ROTAS DE LISTAGEM E CRIAÇÃO ---
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

# --- LÓGICA DE UPLOAD + PROCESSAMENTO ---
async def process_upload_logic(case_id: str, file: UploadFile):
    driver = get_driver()
    print(f"--> Processando Upload para Caso: {case_id}")
    
    # 1. Salvar temporariamente
    file_path = f"{UPLOAD_DIR}/{case_id}_{file.filename}"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        print(f"Erro ao salvar arquivo: {e}")
        return {"status": "error", "detail": "Falha ao salvar arquivo no servidor"}
    
    # 2. Ler PDF
    text_content = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: text_content += text + "\n"
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        # Não falha, tenta continuar se der
    
    # 3. Buscar Nome do Alvo
    target_name = "ALVO"
    with driver.session() as session:
        res = session.run("MATCH (c:Case {id: $id}) RETURN c.title as title", id=case_id).single()
        if res: target_name = res["title"]

    # 4. Extrair Dados (MIND-7 Engine)
    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    
    # 5. Salvar no Grafo (Neo4j)
    count = 0
    with driver.session() as session:
        # Garante o nó da Pessoa (Alvo)
        session.run("""
            MATCH (c:Case {id: $cid})
            MERGE (p:Person {name: $name})
            MERGE (c)-[:INVESTIGATES]->(p)
        """, cid=case_id, name=target_name)

        # Telefones
        for p in phones:
            if p.confidence_score > 30:
                session.run("""
                    MATCH (p:Person {name: $name})
                    MERGE (t:Phone {label: $num})
                    ON CREATE SET t.type = 'phone', t.owner = $owner
                    MERGE (p)-[:HAS_PHONE]->(t)
                """, name=target_name, num=p.number, owner=p.registered_owner)
                count += 1
        
        # Endereços
        for a in addresses:
            session.run("""
                MATCH (p:Person {name: $name})
                MERGE (addr:Address {label: $full})
                ON CREATE SET addr.type = 'address'
                MERGE (p)-[:LIVES_AT]->(addr)
            """, name=target_name, full=a.full_address)
            count += 1

    # Limpeza
    try:
        os.remove(file_path)
    except: pass

    return {"status": "processed", "count": count, "detail": f"Processado com sucesso. {count} novas conexões."}

# --- ROTAS DE UPLOAD DUPLAS (SEM E COM BARRA NO FINAL) ---
# Isso resolve o problema do 404/307 do Proxy
@router.post("/{case_id}/upload")
async def upload_evidence_no_slash(case_id: str, file: UploadFile = File(...)):
    return await process_upload_logic(case_id, file)

@router.post("/{case_id}/upload/")
async def upload_evidence_slash(case_id: str, file: UploadFile = File(...)):
    return await process_upload_logic(case_id, file)

