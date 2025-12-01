import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import time

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = None

def get_driver():
    global driver
    # Se o driver não existe ou está fechado, cria um novo
    if driver is None:
        try:
            if not URI:
                print("⚠️ NEO4J_URI não configurado!")
                return None
            
            # Configuração otimizada para evitar Queda de Conexão
            driver = GraphDatabase.driver(
                URI, 
                auth=(USER, PASSWORD),
                max_connection_lifetime=200,  # Fecha conexões velhas
                max_connection_pool_size=50,  # Limite de conexões
                keep_alive=True               # Mantém vivo
            )
            driver.verify_connectivity()
            print("✅ Neo4j Driver (Re)Conectado!")
        except Exception as e:
            print(f"❌ Erro crítico ao criar driver Neo4j: {e}")
            return None
    
    # Teste rápido de vida antes de devolver
    try:
        driver.verify_connectivity()
    except:
        print("⚠️ Conexão perdida. Tentando reconectar...")
        driver.close()
        driver = None
        return get_driver() # Recursivo (Tenta de novo)

    return driver

def verify_connection():
    get_driver()

def close_connection():
    global driver
    if driver:
        driver.close()
