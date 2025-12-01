from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from app.services.extractor import Mind7Extractor
from app.schemas import InvestigationReport
from app.cases import routes as cases_routes  # IMPORTANTE: Importar rotas de casos
from app.database import verify_connection

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUIR ROTAS DE CASOS ---
# Isso resolve o problema de não criar casos e do erro 404 em /cases
app.include_router(cases_routes.router, prefix="/cases", tags=["Cases"])

@app.on_event("startup")
def startup_event():
    verify_connection()

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "1.3"}

# --- LÓGICA DE PROCESSAMENTO DE PDF ---
async def process_pdf_logic(target_name: str, file: UploadFile):
    print(f"--> Recebendo arquivo: {file.filename} para alvo: {target_name}")
    text_content = ""
    try:
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
    except Exception as e:
        print(f"Erro PDF: {e}")
        text_content = ""

    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()
    
    # Filtro de relevância básico
    relevant_phones = [p for p in phones if p.confidence_score > 30]

    return {
        "target": {
            "name": target_name,
            "cpf": "PENDING",
            "surnames": extractor.target_surnames,
            "raw_text": "Processado",
            "source_pdf": file.filename
        },
        "phones": relevant_phones,
        "addresses": addresses
    }

# --- ROTAS DE ANÁLISE (DUPLAS) ---
@app.post("/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_root(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)

@app.post("/api/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_api(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)
