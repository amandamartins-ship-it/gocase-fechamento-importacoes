"""Fluxo OAuth 2.0 "web" (Client tipo Web application) usando a própria conta
Google da Amanda - ver README para os passos de criação do credentials.json.

Guarda o token localmente em backend/secrets/token.json (fora do banco: é um
segredo, não um dado de negócio, e a pasta secrets/ já está fora do git).
"""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.core.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Estado do CSRF do fluxo OAuth: processo local, usuário único, login->callback
# acontece em segundos no mesmo processo - não precisa de storage persistente.
_pending_state: str | None = None


def _build_flow(state: str | None = None) -> Flow:
    settings = get_settings()
    return Flow.from_client_secrets_file(
        settings.google_oauth_credentials_path,
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
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.google_oauth_token_path), exist_ok=True)
    with open(settings.google_oauth_token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def load_credentials() -> Credentials | None:
    settings = get_settings()
    if not os.path.exists(settings.google_oauth_token_path):
        return None
    with open(settings.google_oauth_token_path, encoding="utf-8") as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)
    return creds


def has_valid_token() -> bool:
    try:
        creds = load_credentials()
    except Exception:
        return False
    return bool(creds and creds.valid)
