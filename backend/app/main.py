import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Importar routers com debug
try:
    from app.api.routers import aprendizado
    logger.info("✓ aprendizado router imported")
except Exception as e:
    logger.error(f"✗ Failed to import aprendizado: {e}")

try:
    from app.api.routers import auth
    logger.info("✓ auth router imported")
except Exception as e:
    logger.error(f"✗ Failed to import auth: {e}")

try:
    from app.api.routers import drive
    logger.info("✓ drive router imported")
except Exception as e:
    logger.error(f"✗ Failed to import drive: {e}")
    drive = None

try:
    from app.api.routers import fechamento, health, processos, rateio, razao
    logger.info("✓ Other routers imported")
except Exception as e:
    logger.error(f"✗ Failed to import other routers: {e}")

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

# Endpoint de diagnóstico ANTES de registrar routers
@app.get("/diag-status")
def diag_status() -> dict:
    """Diagnóstico de status do app"""
    return {
        "app_running": True,
        "drive_imported": drive is not None,
        "drive_is_none": drive is None,
        "message": "app is running"
    }

app.include_router(health.router)
app.include_router(auth.router)
if drive:
    app.include_router(drive.router)
    logger.info("✓ drive router registered")
else:
    logger.warning("✗ drive router NOT registered due to import error")
app.include_router(razao.router)
app.include_router(rateio.router)
app.include_router(fechamento.router)
app.include_router(aprendizado.router)
app.include_router(processos.router)
