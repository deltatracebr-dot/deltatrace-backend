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

# --- FUNÇÕES DE CASOS ---
def create_case(title: str):
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    safe_title = title if title else "Caso Sem Título"
    query = "CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: datetime()}) RETURN c"
    with driver.session() as session:
        session.run(query, id=case_id, title=safe_title)
        return {"id": case_id, "title": safe_title, "status": "Em andamento"}

def get_all_cases():
    query = "MATCH (c:Case) RETURN c.id as id, coalesce(c.title, 'Sem Título') as title, coalesce(c.status, 'Ativo') as status ORDER BY c.created_at DESC"
    try:
        with driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
    except: return []

# --- SMART EXTRACTOR V5 (COM NOME) ---
def extract_entities_from_pdf(file_bytes):
    temp_filename = "temp_upload.pdf"
    with open(temp_filename, "wb") as f: f.write(file_bytes)
    
    results = []
    seen = set()

    try:
        with pdfplumber.open(temp_filename) as pdf:
            for page in pdf.pages:
                # Extrair texto linha por linha para manter contexto
                lines = page.extract_text().split('\n')
                for line in lines:
                    # 1. Busca CPF na linha
                    cpf_match = re.search(r'(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})', line)
                    if cpf_match:
                        cpf_val = cpf_match.group(0)
                        # Remove o CPF da linha para sobrar o nome
                        rest_of_line = line.replace(cpf_val, "").strip()
                        # Limpa lixo comum ("CPF:", "Nome:", pontuação)
                        possible_name = re.sub(r'(CPF|Nome|:|;|-|\.)', '', rest_of_line).strip()
                        
                        # Se sobrou algo relevante, assume que é o nome
                        label_text = f"{cpf_val}\n{possible_name}" if len(possible_name) > 3 else cpf_val
                        
                        u_key = f"CPF:{cpf_val}"
                        if u_key not in seen:
                            results.append({"type": "CPF", "value": label_text}) # Guarda CPF + Nome
                            seen.add(u_key)
                            continue # Se achou CPF, pula proxima checagem na mesma linha

                    # 2. Busca Telefone (Se não for CPF)
                    phone_match = re.search(r'\b(?:[1-9]{2})\s?(?:9\d{4}[-\s]?\d{4}|[2-5]\d{3}[-\s]?\d{4})\b', line)
                    if phone_match:
                        phone_val = phone_match.group(0)
                        u_key = f"PHONE:{phone_val}"
                        if u_key not in seen:
                            results.append({"type": "PHONE", "value": phone_val})
                            seen.add(u_key)

                    # 3. Busca Placa
                    placa_match = re.search(r'\b[A-Z]{3}[-]?[0-9][A-Z0-9][0-9]{2}\b', line)
                    if placa_match:
                        placa_val = placa_match.group(0)
                        u_key = f"PLACA:{placa_val}"
                        if u_key not in seen:
                            results.append({"type": "PLACA", "value": placa_val})
                            seen.add(u_key)
                    
                    # 4. Busca Email
                    email_match = re.search(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', line, re.IGNORECASE)
                    if email_match:
                        email_val = email_match.group(0)
                        u_key = f"EMAIL:{email_val}"
                        if u_key not in seen:
                            results.append({"type": "EMAIL", "value": email_val})
                            seen.add(u_key)

    except Exception as e:
        print(f"PDF Error: {e}")
        return []
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)
    
    return results

def process_upload(case_id: str, file_bytes: bytes):
    entities = extract_entities_from_pdf(file_bytes)
    driver = get_db()
    if not driver: return {"error": "Sem banco"}
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
