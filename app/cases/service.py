import os
import re
import pdfplumber
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Configuração Neo4j
URI = os.getenv("NEO4J_URI", "neo4j+s://9605d472.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD") 

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def extract_entities_from_pdf(file_bytes):
    """
    Lê bytes de um PDF e extrai Entidades (SEM DATAS).
    """
    text = ""
    temp_filename = "temp_upload.pdf"
    
    with open(temp_filename, "wb") as f:
        f.write(file_bytes)
    
    try:
        with pdfplumber.open(temp_filename) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        return []
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    # --- REGEX PATTERNS (V4 - SEM DATA) ---
    patterns = {
        "CPF": r'(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})',
        "CNPJ": r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b',
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE": r'\b(?:[1-9]{2})\s?(?:9\d{4}[-\s]?\d{4}|[2-5]\d{3}[-\s]?\d{4})\b',
        "PLACA": r'\b[A-Z]{3}[-]?[0-9][A-Z0-9][0-9]{2}\b'
        # DATA REMOVIDA PARA EVITAR POLUIÇÃO
    }

    results = []
    seen = set()

    # Ordem de prioridade
    priority_order = ["CPF", "CNPJ", "PLACA", "EMAIL", "PHONE"]

    for label in priority_order:
        pattern = patterns[label]
        matches = re.findall(pattern, text)
        
        for match in matches:
            clean_val = match.strip()
            
            # --- FILTROS DE QUALIDADE ---
            if label == "PHONE":
                nums = re.sub(r'\D', '', clean_val)
                if len(nums) < 10 or len(nums) > 11: continue
                if nums.startswith('0'): continue
            
            if label == "CPF":
                nums = re.sub(r'\D', '', clean_val)
                if len(nums) != 11: continue 
                if len(set(nums)) == 1: continue

            # Chave única
            unique_key = f"{label}:{clean_val.upper()}"
            value_key = clean_val.replace('.', '').replace('-', '').replace('/', '')
            
            is_duplicate = False
            for s in seen:
                if value_key in s.replace('.', '').replace('-', '').replace('/', ''):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                results.append({"type": label, "value": clean_val})
                seen.add(unique_key)
    
    return results

def process_upload(case_id: str, file_bytes: bytes):
    entities = extract_entities_from_pdf(file_bytes)
    
    if not entities:
        return {"message": "Nenhuma entidade encontrada.", "count": 0}

    with driver.session() as session:
        session.execute_write(_create_nodes_tx, case_id, entities)
    
    return {"message": "Processamento concluído", "count": len(entities), "data": entities}

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
