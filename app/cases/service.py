import os
import re
import uuid
import pdfplumber
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j+s://9605d472.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD") 

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def create_case(title: str):
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    # Garante que title nunca seja nulo na criação
    safe_title = title if title else "Caso Sem Título"
    
    query = """
    CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: datetime()})
    RETURN c.id as id, c.title as title, c.status as status
    """
    with driver.session() as session:
        result = session.run(query, id=case_id, title=safe_title).single()
        return result.data()

def get_all_cases():
    # COALESCE: Se o titulo for null, retorna "Sem Título". Proteção direto no banco.
    query = """
    MATCH (c:Case)
    RETURN 
        c.id as id, 
        coalesce(c.title, 'Caso Sem Título') as title, 
        coalesce(c.status, 'Em andamento') as status
    ORDER BY c.created_at DESC
    """
    with driver.session() as session:
        result = session.run(query)
        return [record.data() for record in result]

# --- UPLOAD LOGIC (Mantida) ---
def extract_entities_from_pdf(file_bytes):
    text = ""
    temp_filename = "temp_upload.pdf"
    with open(temp_filename, "wb") as f:
        f.write(file_bytes)
    try:
        with pdfplumber.open(temp_filename) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except:
        return []
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)

    patterns = {
        "CPF": r'(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})',
        "CNPJ": r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b',
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE": r'\b(?:[1-9]{2})\s?(?:9\d{4}[-\s]?\d{4}|[2-5]\d{3}[-\s]?\d{4})\b',
        "PLACA": r'\b[A-Z]{3}[-]?[0-9][A-Z0-9][0-9]{2}\b'
    }
    results = []
    seen = set()
    priority = ["CPF", "CNPJ", "PLACA", "EMAIL", "PHONE"]

    for label in priority:
        matches = re.findall(patterns[label], text)
        for match in matches:
            clean = match.strip()
            if label == "PHONE":
                n = re.sub(r'\D', '', clean)
                if len(n) < 10 or len(n) > 11 or n.startswith('0'): continue
            if label == "CPF":
                n = re.sub(r'\D', '', clean)
                if len(n) != 11 or len(set(n)) == 1: continue
            
            u_key = f"{label}:{clean.upper()}"
            if u_key not in seen:
                results.append({"type": label, "value": clean})
                seen.add(u_key)
    return results

def process_upload(case_id: str, file_bytes: bytes):
    entities = extract_entities_from_pdf(file_bytes)
    if not entities: return {"message": "Nada encontrado.", "count": 0}
    with driver.session() as session:
        session.execute_write(_create_nodes_tx, case_id, entities)
    return {"message": "Processado", "count": len(entities), "data": entities}

def _create_nodes_tx(tx, case_id, entities):
    tx.run("MERGE (c:Case {id: $case_id})", case_id=case_id)
    query = """
    UNWIND $entities as entity
    MATCH (c:Case {id: $case_id})
    MERGE (e:Entity {value: entity.value})
    ON CREATE SET e.type = entity.type, e.created_at = datetime()
    MERGE (c)-[:HAS_EVIDENCE]->(e)
    """
    tx.run(query, case_id=case_id, entities=entities)
