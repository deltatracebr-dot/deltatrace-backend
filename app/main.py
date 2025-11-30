import pdfplumber
from fastapi import UploadFile, File, Form
from app.services.extractor import Mind7Extractor
from app.schemas import InvestigationReport, PersonResult
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Imports dos Routers
from app.auth.routes import router as auth_router
from app.graph_engine.routes import router as graph_router
from app.cases.routes import router as cases_router
from app.core_osint.routes import router as osint_router

app = FastAPI(
    title="DeltaTrace OSINT Core",
    version="1.0.0",
)

# -----------------------------------
# Configuração de CORS (PERMISSIVE - FINAL)
# -----------------------------------
# Permitir tudo. Em produção real, restrinja para o domínio da Vercel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# Healthcheck
# -----------------------------------
@app.get("/health")
def health():
    return {"status": "online", "env": "production", "cors": "permissive"}

# -----------------------------------
# Registro de Rotas
# -----------------------------------
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(graph_router, prefix="/graph", tags=["graph"])
app.include_router(cases_router, prefix="/cases", tags=["cases"])
app.include_router(osint_router, prefix="/osint", tags=["osint"])

# --- ROTA DE INGESTÃO DE INTELIGÊNCIA ---
@app.post("/api/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_mind7(target_name: str = Form(...), file: UploadFile = File(...)):
    print(f"Recebendo arquivo: {file.filename} para alvo: {target_name}")
    
    # 1. Ler o PDF na memória
    text_content = ""
    try:
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text_content += extracted + "\n"
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        # Retorna vazio em caso de erro fatal de leitura, mas não quebra
        text_content = ""

    # 2. Instanciar o Extrator
    extractor = Mind7Extractor(raw_text=text_content, target_name=target_name)

    # 3. Rodar os Módulos de Inteligência
    phones = extractor.extract_phones()
    addresses = extractor.extract_addresses()

    # 4. Filtrar resultados (Curadoria Automática básica)
    # Ex: Telefones com score > 30
    relevant_phones = [p for p in phones if p.confidence_score > 30]

    # 5. Montar resposta estruturada
    return {
        "target": {
            "name": target_name,
            "cpf": "EM BREVE", # Implementar extrator de CPF depois
            "surnames": extractor.target_surnames,
            "raw_text": "Processado via DeltaTrace Engine",
            "source_pdf": file.filename
        },
        "phones": relevant_phones,
        "addresses": addresses
    }
