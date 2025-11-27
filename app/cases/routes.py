from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from . import service

router = APIRouter()

# MODELO BLINDADO
# Se o banco retornar nulo, usamos um valor padrão.
class CaseModel(BaseModel):
    id: str
    title: str = "Caso Sem Título"      # Valor padrão se vier null
    status: str = "Em andamento"        # Valor padrão se vier null

class NewCaseInput(BaseModel):
    title: str

@router.get("/", response_model=List[CaseModel])
def list_cases():
    # Busca do banco real
    return service.get_all_cases()

@router.post("/", response_model=CaseModel)
def create_new_case(input: NewCaseInput):
    return service.create_case(input.title)

@router.post("/{case_id}/upload")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são permitidos.")
    
    content = await file.read()
    
    try:
        result = service.process_upload(case_id, content)
        return result
    except Exception as e:
        # Logar erro no console do servidor para debug
        print(f"Erro no upload: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
