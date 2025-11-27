from fastapi import APIRouter
from app.common.driver import get_db
import math

router = APIRouter()

@router.get("/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_db()
    if not driver: return {"nodes": [], "edges": []}
    
    query = """
    MATCH (c:Case {id: $case_id})
    OPTIONAL MATCH (c)-[r]->(e:Entity)
    RETURN c, collect(e) as entities
    """
    with driver.session() as session:
        result = session.run(query, case_id=case_id).single()
    
    if not result: return {"nodes": [], "edges": []}

    case_node = result["c"]
    entities = result["entities"]
    
    nodes = []
    edges = []
    
    # Nó Central
    nodes.append({
        "id": case_node["id"],
        "type": "input",
        "data": { "label": f"📂 {case_node.get('title', 'Caso')}" },
        "position": { "x": 400, "y": 300 },
        "style": { "background": "#10b981", "color": "white", "border": "none", "borderRadius": "8px", "fontWeight": "bold", "width": 180 }
    })

    # Satélites
    radius = 280
    total = len(entities)
    for i, entity in enumerate(entities):
        if not entity: continue
        angle = (2 * math.pi * i) / total if total > 0 else 0
        x = 400 + radius * math.cos(angle)
        y = 300 + radius * math.sin(angle)
        
        etype = entity.get("type", "UNKNOWN")
        val = entity.get("value", "???")
        
        # --- DIFERENCIAÇÃO VISUAL ---
        bg_color = "#1e293b" # Default Slate
        border_color = "#475569"
        icon = "📄"

        if etype == "CPF": 
            bg_color = "#4f46e5" # Indigo (Roxo Azulado)
            border_color = "#6366f1"
            icon = "👤"
        elif etype == "PHONE": 
            bg_color = "#d97706" # Amber (Laranja)
            border_color = "#f59e0b"
            icon = "📱"
        elif etype == "EMAIL": 
            bg_color = "#0891b2" # Cyan
            border_color = "#22d3ee"
            icon = "📧"
        elif etype == "PLACA": 
            bg_color = "#be123c" # Rose (Vermelho)
            border_color = "#f43f5e"
            icon = "🚗"

        nodes.append({
            "id": f"ent_{i}",
            "data": { "label": f"{icon} {etype}\n{val}" },
            "position": { "x": x, "y": y },
            "style": { 
                "background": bg_color, 
                "color": "white", 
                "border": f"1px solid {border_color}",
                "fontSize": "11px",
                "width": 160,
                "borderRadius": "6px"
            }
        })
        edges.append({
            "id": f"e_{i}", "source": case_node["id"], "target": f"ent_{i}",
            "animated": True, "style": { "stroke": border_color }
        })

    return { "nodes": nodes, "edges": edges }
