from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Any
from pydantic import BaseModel, Field, field_validator
from . import service
import json

router = APIRouter()

class CaseModel(BaseModel):
    id: str
    title: str = Field(default="Caso Sem Título")
    status: str = Field(default="Em andamento")
    
    @field_validator("title", "status", mode="before")
    @classmethod
    def check_none(cls, v: Any):
        return str(v) if v is not None else "Não Informado"

class NewCaseInput(BaseModel):
    title: str

@router.get("/", response_model=List[CaseModel])
def list_cases():
    return service.get_all_cases()

@router.post("/", response_model=CaseModel)
def create_new_case(input: NewCaseInput):
    return service.create_case(input.title)

@router.delete("/{case_id}")
def delete_case(case_id: str):
    success = service.delete_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="Caso não encontrado ou erro ao deletar")
    return {"status": "deleted"}

@router.post("/{case_id}/upload")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas PDF.")
    content = await file.read()
    try: return service.process_upload(case_id, content)
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}/backup")
def backup_case(case_id: str):
    data = service.export_case_data(case_id)
    if not data: raise HTTPException(status_code=404)
    return data

@router.post("/restore")
async def restore_case(file: UploadFile = File(...)):
    content = await file.read()
    try:
        data = json.loads(content)
        if service.import_case_data(data): return {"msg": "ok"}
    except: pass
    raise HTTPException(status_code=400, detail="Erro restore")
