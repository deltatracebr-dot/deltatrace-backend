import os
import re
import uuid
import pdfplumber
from datetime import datetime
from app.db import get_driver

def create_case(title: str):
    driver = get_driver()
    if not driver: 
        # Fallback se o banco não responder
        print("⚠️ Banco indisponível. Retornando erro controlado.")
        return None
    
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    safe_title = title if title else "Caso Sem Título"
    
    query = "CREATE (c:Case {id: $id, title: $title, status: 'Em andamento', created_at: datetime()}) RETURN c"
    try:
        with driver.session() as session:
            session.run(query, id=case_id, title=safe_title)
            return {"id": case_id, "title": safe_title, "status": "Em andamento"}
    except Exception as e:
        print(f"Erro Neo4j Create: {e}")
        return None

def get_all_cases():
    driver = get_driver()
    if not driver: return []
    query = "MATCH (c:Case) RETURN c.id as id, coalesce(c.title, 'Sem Título') as title, coalesce(c.status, 'Ativo') as status ORDER BY c.created_at DESC"
    try:
        with driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
    except: return []

# --- UPLOAD ---
def extract_entities_from_pdf(file_bytes):
    # (Mantendo a mesma lógica de extração V5 que já funcionava)
    # ... (código do regex omitido para brevidade, mas o arquivo manterá o anterior se não sobrescrevermos tudo)
    # VOU REESCREVER O BLOCO DE EXTRAÇÃO COMPLETO PARA GARANTIR QUE NÃO APAGUE
    text = ""
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
                        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                    }
                    for label, pat in patterns.items():
                        match = re.search(pat, line)
                        if match:
                            val = match.group(0)
                            if label == "PHONE" and (len(re.sub(r'\D','',val)) < 10 or val.startswith('0')): continue
                            if f"{label}:{val}" not in seen:
                                results.append({"type": label, "value": val})
                                seen.add(f"{label}:{val}")
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

# --- AGENTE DE BUSCA (OSINT) ---
from duckduckgo_search import DDGS

def search_web_intelligence(query: str, limit: int = 5):
    """
    Realiza uma busca real na web e retorna os resultados estruturados.
    Não abre navegador, o servidor que busca.
    """
    results = []
    try:
        with DDGS() as ddgs:
            # Busca textual
            search_gen = ddgs.text(query, region="br-pt", safesearch="off", max_results=limit)
            for r in search_gen:
                results.append({
                    "title": r.get("title"),
                    "link": r.get("href"),
                    "snippet": r.get("body")
                })
    except Exception as e:
        print(f"Erro na busca OSINT: {e}")
        return [{"title": "Erro na busca", "snippet": str(e), "link": "#"}]
    
    return results
