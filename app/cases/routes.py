from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from . import service
import json

router = APIRouter()

class CaseModel(BaseModel):
    id: str
    title: str = Field(default="Caso Sem Título")
    status: str = Field(default="Em andamento")

    @field_validator('title', 'status', mode='before')
    @classmethod
    def set_default_if_none(cls, v: Any) -> str:
        if v is None: return "Não Informado"
        return str(v)

class NewCaseInput(BaseModel):
    title: str

@router.get("/", response_model=List[CaseModel])
def list_cases():
    try: return service.get_all_cases()
    except: return []

@router.post("/", response_model=CaseModel)
def create_new_case(input: NewCaseInput):
    return service.create_case(input.title)

@router.post("/{case_id}/upload")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas PDF.")
    content = await file.read()
    try: return service.process_upload(case_id, content)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- ROTAS DE BACKUP ---

@router.get("/{case_id}/backup")
def backup_case(case_id: str):
    data = service.export_case_data(case_id)
    if not data:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    return data

@router.post("/restore")
async def restore_case(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .json")
    
    try:
        content = await file.read()
        data = json.loads(content)
        success = service.import_case_data(data)
        if success:
            return {"message": "Caso restaurado com sucesso!"}
        else:
            raise HTTPException(status_code=400, detail="JSON inválido ou corrompido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao restaurar: {str(e)}")
