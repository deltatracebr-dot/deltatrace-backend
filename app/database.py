import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Configurações do Neo4j (Vêm das variáveis de ambiente do Render)
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = None

def get_driver():
    global driver
    if driver is None:
        try:
            if not URI:
                print("⚠️ NEO4J_URI não configurado!")
                return None
            driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        except Exception as e:
            print(f"❌ Erro crítico ao criar driver Neo4j: {e}")
            return None
    return driver

def verify_connection():
    """Testa a conexão ao iniciar o sistema"""
    try:
        drv = get_driver()
        if drv:
            drv.verify_connectivity()
            print("✅ Neo4j Conectado com Sucesso!")
        else:
            print("❌ Driver do Neo4j nulo.")
    except Exception as e:
        print(f"❌ Falha na conexão com Neo4j: {e}")

def close_connection():
    global driver
    if driver:
        driver.close()
