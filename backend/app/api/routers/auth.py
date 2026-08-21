import hmac

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.auth import LoginRequest, TokenResponse
from app.core.config import get_settings
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    settings = get_settings()
    email_ok = hmac.compare_digest(payload.email.lower(), settings.admin_email.lower())
    password_ok = hmac.compare_digest(payload.password, settings.admin_password)
    if not (email_ok and password_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    token = create_access_token(subject=settings.admin_email)
    return TokenResponse(access_token=token)
