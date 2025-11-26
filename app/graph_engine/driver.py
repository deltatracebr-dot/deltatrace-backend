import os
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv

# Carrega variáveis do .env na raiz do backend
load_dotenv()


class Neo4jDriver:
    """
    Wrapper simples para conexão com o Neo4j.

    - Usa NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE do .env
    - execute()  -> consultas em geral (READ ou WRITE simples)
    - write()    -> usada pelo módulo de grafo para criação/alteração
    """

    def __init__(self) -> None:
        self.uri: str = os.getenv("NEO4J_URI", "")
        self.user: str = os.getenv("NEO4J_USER", "")
        self.password: str = os.getenv("NEO4J_PASSWORD", "")
        self.database: str = os.getenv("NEO4J_DATABASE", "neo4j")

        if not self.uri or not self.user or not self.password:
            raise RuntimeError(
                "Configuração do Neo4j ausente. "
                "Defina NEO4J_URI, NEO4J_USER e NEO4J_PASSWORD no .env"
            )

        self.driver: Driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
        )

    # -------------------------
    # EXECUTA QUALQUER QUERY
    # -------------------------
    def execute(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Executa uma query Cypher e retorna uma lista de dicionários.
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    # -------------------------
    # EXECUTA QUERY DE ESCRITA
    # -------------------------
    def write(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Alias semântico para operações de escrita (CREATE/MERGE/SET).
        A implementação é igual ao execute(), mas fica mais claro
        no restante do código.
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    # -------------------------
    # FECHA DRIVER
    # -------------------------
    def close(self) -> None:
        if self.driver:
            self.driver.close()


# Instância global usada pelo app inteiro
neo4j_db = Neo4jDriver()
