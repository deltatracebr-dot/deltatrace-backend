from pydantic import BaseModel
from typing import List, Optional

# --- MODELOS DE INTELIGÊNCIA ---

class EntityBase(BaseModel):
    raw_text: str
    source_pdf: str

class PersonResult(EntityBase):
    name: str
    cpf: str
    surnames: List[str]  # Para análise de DNA familiar

class PhoneResult(EntityBase):
    number: str
    registered_owner: str  # Nome na operadora
    last_link_date: Optional[str] = None
    classification: str  # "Pessoal", "Laranja/Familiar", "Descartado"
    confidence_score: int  # 0 a 100

class AddressResult(EntityBase):
    full_address: str
    associated_names: List[str]
    is_family_hq: bool = False  # A feature "QG da Família"
    match_count: int = 0  # Quantos sobrenomes bateram

class InvestigationReport(BaseModel):
    target: PersonResult
    phones: List[PhoneResult]
    addresses: List[AddressResult]
    # Futuro: Veiculos, Processos...
