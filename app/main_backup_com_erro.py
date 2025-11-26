from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.routes import router as auth_router
from .core_osint.routes import router as osint_router
from .graph_engine.routes import router as graph_router
from .cases.routes import router as cases_router

app = FastAPI(title="Delta Trace OSINT CORE")

# CORS bem aberto para DEV
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Módulos principais
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(osint_router, prefix="/osint", tags=["osint"])

# Módulo de casos (MIND-7, etc.) -> /cases/...
app.include_router(cases_router)

# Módulo de grafo -> /graph/...
app.include_router(graph_router, prefix="/graph", tags=["graph"])
from app.cases.routes import router as cases_router

app.include_router(cases_router, prefix="/cases", tags=["cases"])
