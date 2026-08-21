from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import aprendizado, auth, drive, fechamento, health, processos, rateio, razao

app = FastAPI(
    title="Assistente de Fechamento Contábil de Importações",
    description="Reconstrói automaticamente a composição contábil de cada processo de importação.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
