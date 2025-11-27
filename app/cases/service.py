import os
import re
import uuid
import pdfplumber
from datetime import datetime
from app.db import get_driver

# --- FUNÇÕES DE CASOS ---
def create_case(title: str):
    driver = get_driver()
    if not driver: return None
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    safe_title = title if title else "Caso Sem Título"
    query = "CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: datetime()}) RETURN c"
    try:
        with driver.session() as session:
            result = session.run(query, id=case_id, title=safe_title).single()
            return result.data()
    except: return None

def get_all_cases():
    driver = get_driver()
    if not driver: return []
    query = "MATCH (c:Case) RETURN c.id as id, coalesce(c.title, 'Sem Título') as title, coalesce(c.status, 'Ativo') as status ORDER BY c.created_at DESC"
    try:
        with driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
    except: return []

def delete_case(case_id: str):
    driver = get_driver()
    if not driver: return False
    # Apaga o caso e suas relações (mantém as entidades se estiverem soltas, ou apaga tudo se preferir)
    # Aqui usamos DETACH DELETE c para apagar o caso e desconectar das entidades
    query = "MATCH (c:Case {id: $case_id}) DETACH DELETE c"
    try:
        with driver.session() as session:
            session.run(query, case_id=case_id)
        return True
    except Exception as e:
        print(f"Erro delete: {e}")
        return False

# --- BACKUP ---
def export_case_data(case_id: str):
    driver = get_driver()
    if not driver: return None
    query = """
    MATCH (c:Case {id: $case_id})
    OPTIONAL MATCH (c)-[:HAS_EVIDENCE]->(e:Entity)
    RETURN c as case_data, collect(properties(e)) as entities
    """
    with driver.session() as session:
        result = session.run(query, case_id=case_id).single()
        if not result: return None
        return {"version": "1.0", "timestamp": datetime.now().isoformat(), "case": dict(result["case_data"]), "entities": result["entities"]}

def import_case_data(data: dict):
    driver = get_driver()
    if not driver: return False
    case_info = data.get("case")
    entities = data.get("entities", [])
    if not case_info or "id" not in case_info: return False
    query = """
    MERGE (c:Case {id: $case_id})
    SET c.title = $title, c.status = $status
    WITH c
    UNWIND $entities as ent
    MERGE (e:Entity {value: ent.value})
    ON CREATE SET e.type = ent.type, e.created_at = datetime()
    MERGE (c)-[:HAS_EVIDENCE]->(e)
    """
    try:
        with driver.session() as session:
            session.run(query, case_id=case_info["id"], title=case_info.get("title", "Restaurado"), status=case_info.get("status", "Ativo"), entities=entities)
        return True
    except: return False

# --- UPLOAD ---
def extract_entities_from_pdf(file_bytes):
    temp_filename = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_filename, "wb") as f: f.write(file_bytes)
    results = []
    seen = set()
    try:
        with pdfplumber.open(temp_filename) as pdf:
            for page in pdf.pages:
                lines = page.extract_text().split('\n')
                for line in lines:
                    cpf_match = re.search(r'(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})', line)
                    if cpf_match:
                        cpf_val = cpf_match.group(0)
                        possible_name = re.sub(r'(CPF|Nome|:|;|-|\.|[\d])', '', line.replace(cpf_val, "")).strip()
                        label_text = f"{cpf_val}\n{possible_name}" if len(possible_name) > 3 else cpf_val
                        if f"CPF:{cpf_val}" not in seen:
                            results.append({"type": "CPF", "value": label_text})
                            seen.add(f"CPF:{cpf_val}")
                            continue 
                    patterns = {
                        "PHONE": r'\b(?:[1-9]{2})\s?(?:9\d{4}[-\s]?\d{4}|[2-5]\d{3}[-\s]?\d{4})\b',
                        "PLACA": r'\b[A-Z]{3}[-]?[0-9][A-Z0-9][0-9]{2}\b',
                        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                         "CNPJ": r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b'
                    }
                    for label, pat in patterns.items():
                        match = re.search(pat, line)
                        if match:
                            val = match.group(0)
                            if label == "PHONE" and (len(re.sub(r'\D','',val)) < 10 or val.startswith('0')): continue
                            u_key = f"{label}:{val.upper()}"
                            if u_key not in seen:
                                results.append({"type": label, "value": val})
                                seen.add(u_key)
    except: pass
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)
    return results

def process_upload(case_id: str, file_bytes: bytes):
    entities = extract_entities_from_pdf(file_bytes)
    driver = get_driver()
    if not driver: return {"count": 0}
    with driver.session() as session:
        session.run("MERGE (c:Case {id: $id})", id=case_id)
        query = """
        UNWIND $data as item
        MATCH (c:Case {id: $id})
        MERGE (e:Entity {value: item.value})
        ON CREATE SET e.type = item.type
        MERGE (c)-[:HAS_EVIDENCE]->(e)
        """
        session.run(query, id=case_id, data=entities)
    return {"count": len(entities)}
