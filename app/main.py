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
# Configuração de CORS (PERMISSIVE)
# -----------------------------------
# Permitir tudo para garantir conexão Vercel <-> Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Liberar todas as origens
    allow_credentials=True,
    allow_methods=["*"],  # Liberar todos os métodos (GET, POST, OPTIONS)
    allow_headers=["*"],  # Liberar todos os headers
)

# -----------------------------------
# Healthcheck
# -----------------------------------
@app.get("/health")
def health():
    return {"status": "online", "env": "production", "cors": "open"}

# -----------------------------------
# Registro de Rotas
# -----------------------------------
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(graph_router, prefix="/graph", tags=["graph"])
app.include_router(cases_router, prefix="/cases", tags=["cases"])
app.include_router(osint_router, prefix="/osint", tags=["osint"])
