from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import aprendizado, auth, drive, fechamento, health, processos, rateio, razao
from app.core.config import get_settings

app = FastAPI(
    title="Assistente de Fechamento Contábil de Importações",
    description="Reconstrói automaticamente a composição contábil de cada processo de importação.",
    version="0.1.0",
)

settings = get_settings()

# CORS: Permitir localhost (dev) e produção
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://fechamento-de-importacoes.devgogroup.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(drive.router)
app.include_router(razao.router)
app.include_router(rateio.router)
app.include_router(fechamento.router)
app.include_router(aprendizado.router)
app.include_router(processos.router)
