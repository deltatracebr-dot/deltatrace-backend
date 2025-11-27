from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Any
from pydantic import BaseModel, Field, field_validator
from . import service

router = APIRouter()

# --- MODELO BLINDADO COM VALIDATOR ---
class CaseModel(BaseModel):
    id: str
    title: str = Field(default="Caso Sem Título")
    status: str = Field(default="Em andamento")

    # O Segredo: 'mode=before' pega o valor ANTES da validação
    # Se vier None do banco, ele troca pelo texto na marra.
    @field_validator('title', 'status', mode='before')
    @classmethod
    def set_default_if_none(cls, v: Any) -> str:
        if v is None:
            return "Não Informado"
        return str(v)

class NewCaseInput(BaseModel):
    title: str

@router.get("/", response_model=List[CaseModel])
def list_cases():
    try:
        # Busca os dados brutos
        cases = service.get_all_cases()
        return cases
    except Exception as e:
        print(f"Erro ao listar casos: {e}")
        return []

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
