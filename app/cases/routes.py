from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List
import uuid
import shutil
import os
import pdfplumber
from app.database import get_driver
from app.services.extractor import Mind7Extractor

router = APIRouter()

# --- DIRETÓRIO DE ARQUIVOS ---
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- MODELOS ---
class Case(BaseModel):
    id: str
    title: str
    status: str
    created_at: str

from pydantic import BaseModel

# --- ROTAS ---

@router.get("/")
def list_cases():
    driver = get_driver()
    cases = []
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
    import datetime
    
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

# --- O PULO DO GATO: UPLOAD COM PROCESSAMENTO AUTOMÁTICO ---
@router.post("/{case_id}/upload")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    driver = get_driver()
    
    # 1. Salvar o arquivo (Backup físico)
    file_path = f"{UPLOAD_DIR}/{case_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Ler o PDF para extração
    text_content = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text: text_content += text + "\n"
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        return {"status": "saved_only", "detail": "Arquivo salvo, mas não processado (PDF ilegível)."}

    # 3. Descobrir o Nome do Alvo pelo Caso
    target_name = "ALVO DESCONHECIDO"
    with driver.session() as session:
        result = session.run("MATCH (c:Case {id: $id}) RETURN c.title as title", id=case_id).single()
        if result:
            target_name = result["title"]

    # 4. Rodar a Inteligência (Extractor)
    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    
    # 5. Gravar Automaticamente no Grafo
    count_nodes = 0
    with driver.session() as session:
        # Salva Telefones
        for p in phones:
            if p.confidence_score > 30: # Filtra lixo
                session.run("""
                    MATCH (c:Case {id: $case_id})
                    MERGE (t:Phone {label: $number})
                    ON CREATE SET t.type = 'phone', t.owner = $owner
                    MERGE (c)-[:RELATED_TO]->(t)
                """, case_id=case_id, number=p.number, owner=p.registered_owner)
                count_nodes += 1

        # Salva Endereços
        for a in addresses:
            session.run("""
                MATCH (c:Case {id: $case_id})
                MERGE (addr:Address {label: $full})
                ON CREATE SET addr.type = 'address'
                MERGE (c)-[:RELATED_TO]->(addr)
            """, case_id=case_id, full=a.full_address)
            count_nodes += 1
            
        # Salva Placas (Se houver lógica de placas no extrator)
        # (O extrator já retorna placas como "PhoneResult" com label especial, então já cai no loop acima)

    return {
        "status": "processed", 
        "count": count_nodes, 
        "detail": f"Processado! {count_nodes} novas conexões criadas."
    }

# --- ROTA DE IMPORTAÇÃO MANUAL (Vinda da Mesa de Análise) ---
@router.post("/{case_id}/import_intel")
def import_intelligence(case_id: str, payload: dict):
    driver = get_driver()
    target_name = payload.get("target", {}).get("name", "ALVO")
    phones = payload.get("phones", [])
    addresses = payload.get("addresses", [])
    
    count = 0
    with driver.session() as session:
        # Cria Alvo
        session.run("""
            MATCH (c:Case {id: $case_id})
            MERGE (p:Person {label: $name})
            ON CREATE SET p.type = 'person'
            MERGE (c)-[:INVESTIGATES]->(p)
        """, case_id=case_id, name=target_name.upper())

        # Salva Telefones
        for p in phones:
            if p.get("confidence_score", 0) > 30:
                session.run("""
                    MATCH (p:Person {label: $name})
                    MERGE (t:Phone {label: $number})
                    ON CREATE SET t.type = 'phone', t.owner = $owner
                    MERGE (p)-[:HAS_PHONE]->(t)
                """, name=target_name.upper(), number=p["number"], owner=p.get("registered_owner", ""))
                count += 1

        # Salva Endereços
        for a in addresses:
            session.run("""
                MATCH (p:Person {label: $name})
                MERGE (addr:Address {label: $full})
                ON CREATE SET addr.type = 'address'
                MERGE (p)-[:LIVES_AT]->(addr)
            """, name=target_name.upper(), full=a["full_address"])
            count += 1

    return {"status": "success", "nodes_added": count}
