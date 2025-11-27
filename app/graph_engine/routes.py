from fastapi import APIRouter
from app.db import get_driver # Usando o mesmo Singleton
import math

router = APIRouter()

@router.get("/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver: return {"nodes": [], "edges": []}
    
    query = """
    MATCH (c:Case {id: $case_id})
    OPTIONAL MATCH (c)-[r]->(e:Entity)
    RETURN c, collect(e) as entities
    """
    try:
        with driver.session() as session:
            result = session.run(query, case_id=case_id).single()
            if not result: return {"nodes": [], "edges": []}
            
            case_node = result["c"]
            entities = result["entities"]
            
            # (Mantendo lógica de nós e cores igual estava...)
            nodes = [{"id": case_node["id"], "type": "input", "data": {"label": f"📂 {case_node.get('title','Case')}"}, "position": {"x":400,"y":300}, "style": {"background":"#10b981", "color":"white", "width":180}}]
            edges = []
            
            total = len(entities)
            for i, ent in enumerate(entities):
                if not ent: continue
                angle = (2 * math.pi * i) / total if total > 0 else 0
                x = 400 + 280 * math.cos(angle)
                y = 300 + 280 * math.sin(angle)
                
                # Cores
                t = ent.get("type", "UNK")
                bg = "#1e293b"
                if t == "CPF": bg = "#4f46e5"
                elif t == "PHONE": bg = "#d97706"
                elif t == "PLACA": bg = "#be123c"
                elif t == "EMAIL": bg = "#0891b2"
                
                nodes.append({
                    "id": f"e_{i}", 
                    "data": {"label": f"{ent.get('value')}"}, 
                    "position": {"x":x, "y":y},
                    "style": {"background": bg, "color":"white", "fontSize":"11px", "width":160}
                })
                edges.append({"id": f"rel_{i}", "source": case_node["id"], "target": f"e_{i}", "animated":True, "style":{"stroke":"#475569"}})
                
            return {"nodes": nodes, "edges": edges}
    except Exception as e:
        print(f"Erro grafo: {e}")
        return {"nodes": [], "edges": []}
