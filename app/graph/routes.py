from fastapi import APIRouter, HTTPException
from app.database import get_driver

router = APIRouter()

@router.get("/case/{case_id}")
def get_case_graph(case_id: str):
    driver = get_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Banco de dados desconectado")

    nodes = []
    edges = []
    
    with driver.session() as session:
        # Busca nós e relacionamentos do caso
        result = session.run("""
            MATCH (c:Case {id: $case_id})-[r1*1..2]-(n)
            OPTIONAL MATCH (n)-[r2]-(m)
            RETURN c, n, r2, m
        """, case_id=case_id)
        
        # Se não achar nada, tenta buscar só o nó do caso
        if result.peek() is None:
             result = session.run("MATCH (c:Case {id: $case_id}) RETURN c", case_id=case_id)

        # Processamento simplificado para gerar JSON do ReactFlow
        # (Lógica básica para evitar erro vazio)
        seen_nodes = set()
        
        for record in result:
            # Processa Nós
            for item in record:
                if hasattr(item, "labels"): # É um nó
                    node_id = item.element_id if hasattr(item, "element_id") else str(item.id)
                    if node_id in seen_nodes: continue
                    seen_nodes.add(node_id)
                    
                    label = list(item.labels)[0] if item.labels else "Unknown"
                    props = dict(item.items())
                    name = props.get("name") or props.get("label") or props.get("title") or "Sem Nome"
                    
                    nodes.append({
                        "id": node_id,
                        "type": "default",
                        "data": { "label": f"{label}\n{name}" },
                        "position": { "x": 0, "y": 0 } # Posição será calculada pelo front
                    })

    return {"nodes": nodes, "edges": edges}
