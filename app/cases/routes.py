from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from pydantic import BaseModel

# Importa o service que acabamos de criar
from . import service

router = APIRouter()

class CaseModel(BaseModel):
    id: str
    title: str
    status: str

# Mock Database para listar casos (simulação rápida para o front funcionar)
FAKE_CASES = [
    {"id": "caso_001", "title": "Operação Delta", "status": "Em andamento"},
    {"id": "caso_002", "title": "Investigação Financeira X", "status": "Arquivado"},
]

@router.get("/", response_model=List[CaseModel])
def list_cases():
    return FAKE_CASES

@router.post("/{case_id}/upload")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    """
    Recebe PDF, extrai dados e popula o Grafo.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são permitidos.")
    
    content = await file.read()
    
    try:
        result = service.process_upload(case_id, content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
