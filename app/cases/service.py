import os
import re
import uuid
import pdfplumber
from app.common.driver import get_db
from datetime import datetime

# --- FUNÇÕES ---
def create_case(title: str):
    driver = get_db()
    if not driver: return None
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    safe_title = title if title else "Caso Sem Título"
    
    query = "CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: datetime()}) RETURN c"
    with driver.session() as session:
        session.run(query, id=case_id, title=safe_title)
        return {"id": case_id, "title": safe_title, "status": "Em andamento"}

def get_all_cases():
    driver = get_db()
    if not driver: return []
    query = "MATCH (c:Case) RETURN c.id as id, coalesce(c.title, 'Sem Título') as title, coalesce(c.status, 'Ativo') as status ORDER BY c.created_at DESC"
    try:
        with driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
    except Exception as e:
        print(f"Erro ao buscar casos: {e}")
        return []

# --- UPLOAD LOGIC ---
def extract_entities_from_pdf(file_bytes):
    text = ""
    # ... (Mantendo a lógica de extração do PDF igual a anterior) ...
    # Simplificando aqui para caber no script, mas o Regex V4 continua valendo
    temp_filename = "temp_upload.pdf"
    with open(temp_filename, "wb") as f: f.write(file_bytes)
    try:
        with pdfplumber.open(temp_filename) as pdf:
            for page in pdf.pages: text += (page.extract_text() or "") + "\n"
    except: return []
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)

    patterns = {
        "CPF": r"(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})",
        "PHONE": r"\b(?:[1-9]{2})\s?(?:9\d{4}[-\s]?\d{4}|[2-5]\d{3}[-\s]?\d{4})\b",
        "PLACA": r"\b[A-Z]{3}[-]?[0-9][A-Z0-9][0-9]{2}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    }
    
    results = []
    seen = set()
    
    for label, pattern in patterns.items():
        matches = re.findall(pattern, text)
        for match in matches:
            clean = match.strip()
            # Filtros básicos
            if label == "PHONE":
                n = re.sub(r"\D", "", clean)
                if len(n) < 10 or len(n) > 11 or n.startswith("0"): continue
            if label == "CPF":
                n = re.sub(r"\D", "", clean)
                if len(n) != 11: continue

            u_key = f"{label}:{clean.upper()}"
            if u_key not in seen:
                results.append({"type": label, "value": clean})
                seen.add(u_key)
    return results

def process_upload(case_id: str, file_bytes: bytes):
    entities = extract_entities_from_pdf(file_bytes)
    driver = get_db()
    if not driver: return {"error": "Sem conexão com banco"}
    
    with driver.session() as session:
        session.execute_write(_create_nodes_tx, case_id, entities)
    return {"message": "Processado", "count": len(entities)}

def _create_nodes_tx(tx, case_id, entities):
    tx.run("MERGE (c:Case {id: $case_id})", case_id=case_id)
    query = """
    UNWIND $entities as entity
    MATCH (c:Case {id: $case_id})
    MERGE (e:Entity {value: entity.value})
    ON CREATE SET e.type = entity.type
    MERGE (c)-[:HAS_EVIDENCE]->(e)
    """
    tx.run(query, case_id=case_id, entities=entities)
