# backend/app/api/graph.py
from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase

router = APIRouter()

driver = GraphDatabase.driver("neo4j+s://<AURADB_URL>", auth=("neo4j", "<PASSWORD>"))

@router.get("/node/{node_id}")
def get_node_details(node_id: str):
    with driver.session() as session:
        query = """
        MATCH (n {id: $id})
        RETURN properties(n) AS props, labels(n) AS labels
        """
        result = session.run(query, id=node_id).single()

        if not result:
            raise HTTPException(status_code=404, detail="Nó não encontrado")

        return {
            "id": node_id,
            "labels": result["labels"],
            "properties": result["props"]
        }
