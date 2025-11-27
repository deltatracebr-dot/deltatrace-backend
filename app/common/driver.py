import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import time

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j+s://9605d472.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

class Neo4jConnection:
    def __init__(self):
        self._driver = None

    def get_driver(self):
        if self._driver is None:
            self._connect()
        return self._driver

    def _connect(self):
        try:
            self._driver = GraphDatabase.driver(
                URI, 
                auth=(USER, PASSWORD),
                max_connection_lifetime=200,  # Renova conexões a cada 3 min
                keep_alive=True
            )
            self._driver.verify_connectivity()
            print("✅ Conexão Neo4j estabelecida/renovada.")
        except Exception as e:
            print(f"❌ Falha ao conectar Neo4j: {e}")
            self._driver = None

    def close(self):
        if self._driver:
            self._driver.close()

# Instância única (Singleton)
db = Neo4jConnection()

def get_db():
    return db.get_driver()
