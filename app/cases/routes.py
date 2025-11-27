from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from . import service

router = APIRouter()

# Modelo tolerante a falhas (aceita None e converte)
class CaseModel(BaseModel):
    id: str
    title: Optional[str] = "Sem Título"
    status: Optional[str] = "Em andamento"

class NewCaseInput(BaseModel):
    title: str

@router.get("/", response_model=List[CaseModel])
def list_cases():
    return service.get_all_cases()

@router.post("/", response_model=CaseModel)
def create_new_case(input: NewCaseInput):
    return service.create_case(input.title)

@router.post("/{case_id}/upload")
async def upload_evidence(case_id: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas PDF.")
    content = await file.read()
    try:
        return service.process_upload(case_id, content)
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
