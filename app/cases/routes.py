from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import List
from pydantic import BaseModel
from . import service

router = APIRouter()

class CaseModel(BaseModel):
    id: str
    title: str
    status: str

class NewCaseInput(BaseModel):
    title: str

@router.get("/", response_model=List[CaseModel])
def list_cases():
    # Agora busca do banco real, não mais mock
    return service.get_all_cases()

@router.post("/", response_model=CaseModel)
def create_new_case(input: NewCaseInput):
    # Cria caso real no Neo4j
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
        raise HTTPException(status_code=500, detail=str(e))
