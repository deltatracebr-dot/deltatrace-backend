from datetime import datetime
from typing import Optional, Dict

from pydantic import BaseModel


class CaseBase(BaseModel):
    title: str
    client: Optional[str] = None
    summary: Optional[str] = None


class CaseCreate(CaseBase):
    """Payload para criação de caso via API."""
    pass


class CaseRead(CaseBase):
    """Caso retornado pela API."""
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class Mind7IngestResult(BaseModel):
    """Resposta do endpoint de ingestão de PDF Mind7."""
    case: CaseRead
    entities_created: Dict[str, int]
