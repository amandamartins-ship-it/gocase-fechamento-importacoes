"""Fluxo OAuth 2.0 "web" (Client tipo Web application) usando a própria conta
Google da Amanda - ver README para os passos de criação do credentials.json.

Token é persistido no PostgreSQL (tabela oauth_tokens) para garantir sobrevivência
a restarts, deploys e reconstrução de containers em produção (GoDeploy).
"""

import json
import os
import logging

from app.core.config import get_settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import OAuthToken

logger = logging.getLogger(__name__)

# Importar Google Auth dependencies com fallback gracioso
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    GOOGLE_AUTH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Google Auth não disponível: {e}. OAuth will not function.")
    GOOGLE_AUTH_AVAILABLE = False
    Request = None
    Credentials = None
    Flow = None

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_NAME = "google_drive"

# Estado do CSRF do fluxo OAuth: processo local, usuário único, login->callback
# acontece em segundos no mesmo processo - não precisa de storage persistente.
_pending_state: str | None = None


def _load_credentials_config() -> dict:
    """Carrega configuração OAuth do Google (credentials.json).

    Tenta em ordem:
    1. Variável de ambiente GOOGLE_OAUTH_CREDENTIALS_JSON (JSON string - GoDeploy Secret)
    2. Arquivo em GOOGLE_OAUTH_CREDENTIALS_PATH (desenvolvimento local)

    Raises:
        FileNotFoundError: Se nenhuma fonte for encontrada
    """
    settings = get_settings()

    # Prioritário: Secret do GoDeploy
    if settings.google_oauth_credentials_json:
        try:
            return json.loads(settings.google_oauth_credentials_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"GOOGLE_OAUTH_CREDENTIALS_JSON não é um JSON válido: {e}") from e

    # Fallback: arquivo local (desenvolvimento)
    if os.path.exists(settings.google_oauth_credentials_path):
        with open(settings.google_oauth_credentials_path, encoding="utf-8") as f:
            return json.load(f)

    raise FileNotFoundError(
        f"credentials.json não encontrado em {settings.google_oauth_credentials_path} "
        "e GOOGLE_OAUTH_CREDENTIALS_JSON não configurada. Veja o README (Fase 2)."
    )


def _build_flow(state: str | None = None):
    if not GOOGLE_AUTH_AVAILABLE:
        raise RuntimeError("Google Auth libraries not installed. Install google-auth, google-auth-oauthlib, google-api-python-client")

    settings = get_settings()
    creds_config = _load_credentials_config()

    return Flow.from_client_config(
        creds_config,
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
        state=state,
    )


def get_authorization_url() -> str:
    global _pending_state
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    _pending_state = state
    return auth_url


def exchange_code(code: str, state: str | None) -> None:
    global _pending_state
    flow = _build_flow(state=state or _pending_state)
    flow.fetch_token(code=code)
    _save_credentials(flow.credentials)
    _pending_state = None


def _save_credentials(creds: Credentials) -> None:
    """Salva credenciais no PostgreSQL (tabela oauth_tokens).

    Em produção, isso garante persistência a restarts, deploys e container rebuilds.
    Em desenvolvimento local, fallback mantém arquivo para compatibilidade.
    """
    token_data = json.loads(creds.to_json())

    session = SessionLocal()
    try:
        # Atualizar ou criar registro
        record = session.query(OAuthToken).filter_by(service_name=SERVICE_NAME).first()
        if record:
            record.token_data = token_data
            # SQLAlchemy atualiza atualizado_em automaticamente via onupdate=func.now()
        else:
            record = OAuthToken(service_name=SERVICE_NAME, token_data=token_data)
            session.add(record)
        session.commit()
    except Exception:
        session.rollback()
        # Fallback: salvar em arquivo local (importante para desenvolvimento/tests)
        settings = get_settings()
        os.makedirs(os.path.dirname(settings.google_oauth_token_path), exist_ok=True)
        with open(settings.google_oauth_token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    finally:
        session.close()


def load_credentials():
    """Carrega credenciais do PostgreSQL (ou arquivo como fallback).

    Prioriza PostgreSQL (produção), fallback para arquivo (desenvolvimento).
    Auto-refresh automático se token expirado.
    """
    if not GOOGLE_AUTH_AVAILABLE:
        logger.warning("Google Auth not available - returning None")
        return None

    session = SessionLocal()
    try:
        record = session.query(OAuthToken).filter_by(service_name=SERVICE_NAME).first()
        if not record:
            # Fallback: tentar carregar de arquivo local
            settings = get_settings()
            if not os.path.exists(settings.google_oauth_token_path):
                return None
            with open(settings.google_oauth_token_path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = record.token_data
    finally:
        session.close()

    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)
    return creds


def has_valid_token() -> bool:
    """Verifica se existe um token válido persistido."""
    try:
        creds = load_credentials()
    except Exception:
        return False
    return bool(creds and creds.valid)
