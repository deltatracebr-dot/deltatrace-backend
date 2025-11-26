from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Configuração Neo4j
URI = os.getenv("NEO4J_URI", "neo4j+s://9605d472.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

@router.get("/case/{case_id}")
def get_case_graph(case_id: str):
    """
    Retorna o JSON pronto para o React Flow:
    - Nodes: O Caso (centro) e as Evidências (satélites)
    - Edges: As linhas conectando eles
    """
    query = """
    MATCH (c:Case {id: $case_id})
    OPTIONAL MATCH (c)-[r]->(e:Entity)
    RETURN c, collect(e) as entities
    """
    
    with driver.session() as session:
        result = session.run(query, case_id=case_id).single()
    
    if not result:
        raise HTTPException(status_code=404, detail="Caso não encontrado")

    case_node = result["c"]
    entities = result["entities"]

    nodes = []
    edges = []

    # 1. Criar o Nó Central (O Caso)
    nodes.append({
        "id": case_node["id"],
        "type": "input", # Destaca que é o pai
        "data": { "label": f"📂 {case_node.get('title', 'Caso')}" },
        "position": { "x": 400, "y": 300 }, # Centro da tela
        "style": { 
            "background": "#10b981", # Emerald 500
            "color": "white", 
            "border": "1px solid #059669", 
            "width": 180,
            "borderRadius": "8px",
            "fontWeight": "bold"
        }
    })

    # 2. Criar os Nós Satélites (Evidências) em círculo
    import math
    radius = 250
    total = len(entities)
    
    for i, entity in enumerate(entities):
        if not entity: continue
        
        # Matemática para distribuir em círculo
        angle = (2 * math.pi * i) / total if total > 0 else 0
        x = 400 + radius * math.cos(angle)
        y = 300 + radius * math.sin(angle)

        # Ícone baseado no tipo
        etype = entity.get("type", "UNKNOWN")
        icon = "📄"
        if etype == "CPF": icon = "👤"
        elif etype == "EMAIL": icon = "📧"
        elif etype == "PHONE": icon = "📱"
        elif etype == "IP": icon = "🌐"

        val = entity.get("value", "???")

        nodes.append({
            "id": f"ent_{i}", # ID único visual
            "data": { "label": f"{icon} {etype}\n{val}" },
            "position": { "x": x, "y": y },
            "style": { 
                "background": "#1e293b", # Slate 800
                "color": "#e2e8f0", 
                "border": "1px solid #475569",
                "fontSize": "12px",
                "width": 150
            }
        })

        # Criar a linha (Edge)
        edges.append({
            "id": f"e_{case_node['id']}-{i}",
            "source": case_node["id"],
            "target": f"ent_{i}",
            "animated": True,
            "style": { "stroke": "#10b981" }
        })

    return { "nodes": nodes, "edges": edges }
