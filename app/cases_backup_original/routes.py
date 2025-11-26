from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Router de Casos
router = APIRouter(prefix="/cases", tags=["Cases"])

# Pasta onde os casos serão salvos
BASE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cases"
BASE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = BASE_DIR / "cases_index.json"


# --------- MODELOS ---------

class CaseCreate(BaseModel):
    title: str
    client: Optional[str] = None
    description: Optional[str] = None


class CaseOut(CaseCreate):
    id: str
    created_at: datetime


# --------- FUNÇÕES AUXILIARES ---------

def _load_cases() -> List[dict]:
    if not INDEX_FILE.exists():
        return []
    try:
        with INDEX_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Se o arquivo estiver corrompido, começa vazio
        return []


def _save_cases(cases: List[dict]) -> None:
    with INDEX_FILE.open("w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2, default=str)


# --------- ENDPOINTS ---------

@router.get("/", response_model=List[CaseOut])
def list_cases() -> List[CaseOut]:
    """Lista todos os casos cadastrados."""
    return _load_cases()


@router.post("/", response_model=CaseOut, status_code=201)
def create_case(case: CaseCreate) -> CaseOut:
    """Cria um novo caso simples."""
    cases = _load_cases()

    new_case = {
        "id": str(uuid.uuid4()),
        "title": case.title,
        "client": case.client,
        "description": case.description,
        "created_at": datetime.utcnow().isoformat(),
    }

    cases.append(new_case)
    _save_cases(cases)
    return new_case
