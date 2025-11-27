import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "neo4j+s://9605d472.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

class Neo4jManager:
    def __init__(self):
        self.driver = None

    def connect(self):
        # Só conecta se ainda não tiver driver
        if not self.driver:
            try:
                print("🔌 Iniciando conexão Neo4j sob demanda...")
                self.driver = GraphDatabase.driver(
                    URI, 
                    auth=(USER, PASSWORD),
                    max_connection_lifetime=300
                )
                self.driver.verify_connectivity()
                print("✅ Neo4j Conectado!")
            except Exception as e:
                print(f"❌ Erro crítico Neo4j: {e}")
                self.driver = None
        return self.driver

    def close(self):
        if self.driver:
            self.driver.close()

# Instância Global
db = Neo4jManager()

def get_driver():
    return db.connect()
