from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from app.services.extractor import Mind7Extractor
from app.schemas import InvestigationReport, PersonResult

app = FastAPI()

# Configuração de CORS (Permitir tudo para evitar bloqueios do Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROTA DE HEALTCHECK (Para saber se está vivo) ---
@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "1.2"}

# --- LÓGICA DE PROCESSAMENTO (Isolada) ---
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
        print(f"Erro Crítico ao ler PDF: {e}")
        text_content = ""

    # Instanciar Extrator
    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)

    # Rodar Módulos
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()

    # Filtro de Relevância (Score > 30)
    relevant_phones = [p for p in phones if p.confidence_score > 30]

    return {
        "target": {
            "name": target_name,
            "cpf": "PENDING",
            "surnames": extractor.target_surnames,
            "raw_text": "Processado com Sucesso",
            "source_pdf": file.filename
        },
        "phones": relevant_phones,
        "addresses": addresses
    }

# --- ROTAS DUPLAS (Aceita com ou sem /api) ---
# Isso resolve o problema do Proxy de uma vez por todas.

@app.post("/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_root(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)

@app.post("/api/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_api(target_name: str = Form(...), file: UploadFile = File(...)):
    return await process_pdf_logic(target_name, file)

