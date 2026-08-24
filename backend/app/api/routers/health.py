import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/debug")
def debug_info() -> dict:
    """Debug endpoint to check import and module status"""
    import sys

    info = {
        "status": "ok",
        "drive_module_in_sys": "app.api.routers.drive" in sys.modules,
        "oauth_module_in_sys": "app.infrastructure.drive.oauth" in sys.modules,
    }

    # Try to import drive and show result
    try:
        from app.api.routers import drive
        info["drive_import_success"] = True
        info["drive_has_router"] = hasattr(drive, 'router')
    except Exception as e:
        info["drive_import_success"] = False
        info["drive_import_error"] = str(e)

    # Try to import oauth and show result
    try:
        from app.infrastructure.drive import oauth
        info["oauth_import_success"] = True
        info["google_auth_available"] = getattr(oauth, 'GOOGLE_AUTH_AVAILABLE', False)
    except Exception as e:
        info["oauth_import_success"] = False
        info["oauth_import_error"] = str(e)

    return info
