import logging
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Variáveis de diagnóstico
drive_import_error = None

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
    logger.exception("✗ ERRO AO IMPORTAR DRIVE - TRACEBACK COMPLETO:")
    drive = None
    drive_import_error = traceback.format_exc()

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
    """Diagnóstico completo de status do app e routers"""
    # Coletar todas as rotas registradas
    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path:
            routes.append({
                "path": path,
                "methods": sorted(list(methods)) if methods else []
            })

    # Verificar se /drive/oauth/status está registrada
    drive_oauth_status_registered = any(
        r["path"] == "/drive/oauth/status" for r in routes
    )

    return {
        "app_running": True,
        "drive_imported": drive is not None,
        "drive_router_exists": bool(drive and hasattr(drive, "router")),
        "drive_router_registered": drive_oauth_status_registered,
        "drive_import_error": drive_import_error,
        "all_routes": sorted(routes, key=lambda r: r["path"]),
        "drive_related_routes": [r for r in routes if "drive" in r["path"] or "oauth" in r["path"]]
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
