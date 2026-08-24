from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.drive import (
    AuthorizationUrlResponse,
    DriveStatusResponse,
    ResumoSincronizacaoResponse,
)
from app.application.use_cases.descobrir_processos import DescobrirProcessosUseCase
from app.infrastructure.classification.keyword_classifier import (
    DocumentClassifierComAprendizado,
    KeywordDocumentClassifier,
)
from app.infrastructure.db.session import get_db
from app.infrastructure.drive import oauth
from app.infrastructure.drive.client import DriveAuthError, GoogleDriveRepository
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository
from app.infrastructure.repositories.regras_aprendidas_repository import SqlAlchemyRegrasAprendidasRepository

router = APIRouter(prefix="/drive", tags=["drive"])


@router.get("/health")
def drive_health() -> dict:
    """Endpoint de teste para verificar se o router está carregado"""
    return {"status": "drive router is loaded"}


@router.get("/oauth/login", response_model=AuthorizationUrlResponse)
def oauth_login(_email: str = Depends(get_current_user)) -> AuthorizationUrlResponse:
    try:
        url = oauth.get_authorization_url()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="credentials.json não encontrado em backend/secrets/ - veja o README (Fase 2).",
        ) from exc
    return AuthorizationUrlResponse(authorization_url=url)


@router.get("/oauth/callback", response_class=HTMLResponse)
def oauth_callback(code: str = Query(...), state: str | None = Query(None)) -> str:
    # Endpoint de redirecionamento do Google - não carrega o Bearer token do app,
    # por isso não é protegido por get_current_user; o "state" faz o papel de CSRF token.
    try:
        oauth.exchange_code(code, state)
    except Exception as exc:  # noqa: BLE001 - qualquer falha aqui vira uma mensagem clara na tela
        return f"<h1>Falha ao conectar ao Google Drive</h1><p>{exc}</p>"
    return (
        "<h1>Conectado ao Google Drive</h1>"
        "<p>Pode fechar esta aba e voltar para o sistema de fechamento.</p>"
    )


@router.get("/oauth/status", response_model=DriveStatusResponse)
def oauth_status(_email: str = Depends(get_current_user)) -> DriveStatusResponse:
    return DriveStatusResponse(conectado=oauth.has_valid_token())


@router.post("/sincronizar", response_model=ResumoSincronizacaoResponse)
def sincronizar(
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumoSincronizacaoResponse:
    classifier = DocumentClassifierComAprendizado(
        KeywordDocumentClassifier(), SqlAlchemyRegrasAprendidasRepository(db)
    )
    drive_repo = GoogleDriveRepository(classifier)
    processo_repo = SqlAlchemyProcessoRepository(db)
    use_case = DescobrirProcessosUseCase(drive_repo, processo_repo)
    try:
        resumo = use_case.executar()
    except DriveAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResumoSincronizacaoResponse(
        total_processos=resumo.total_processos,
        total_embarques=resumo.total_embarques,
        total_documentos=resumo.total_documentos,
        documentos_por_tipo=resumo.documentos_por_tipo,
        processos=resumo.processos,
    )
