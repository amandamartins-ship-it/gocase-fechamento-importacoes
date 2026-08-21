from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.rateio import AuditoriaRateioResponse, ResumoAplicacaoRateioResponse
from app.application.use_cases.aplicar_rateio import REFERENCIA_TIPO_RATEIO_LANCAMENTO, AplicarRateioUseCase
from app.core.config import get_settings
from app.infrastructure.classification.keyword_classifier import KeywordDocumentClassifier
from app.infrastructure.db.session import get_db
from app.infrastructure.drive.client import DriveAuthError, GoogleDriveRepository
from app.infrastructure.repositories.rateio_repository import SqlAlchemyAuditoriaRepository, SqlAlchemyRateioRepository
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository
from app.infrastructure.xlsx.controle_importacoes import ControleImportacoesRateioBuilder

router = APIRouter(prefix="/rateio", tags=["rateio"])


@router.post("/aplicar", response_model=ResumoAplicacaoRateioResponse)
def aplicar_rateio(
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumoAplicacaoRateioResponse:
    settings = get_settings()
    drive_repo = GoogleDriveRepository(KeywordDocumentClassifier())
    try:
        arquivo_id = drive_repo.encontrar_arquivo_por_nome("Controle de Importações.xlsx")
        if arquivo_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Controle de Importações.xlsx não encontrado no Drive da conta autenticada.",
            )
        conteudo = drive_repo.baixar_conteudo(arquivo_id)
    except DriveAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    rateio_builder = ControleImportacoesRateioBuilder(conteudo)
    use_case = AplicarRateioUseCase(
        razao_repo=SqlAlchemyRazaoRepository(db),
        rateio_builder=rateio_builder,
        rateio_repo=SqlAlchemyRateioRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaRepository(db),
    )
    resumo = use_case.executar(mes_referencia.replace(day=1))
    return ResumoAplicacaoRateioResponse(
        total_lancamentos_multi_processo=resumo.total_lancamentos_multi_processo,
        aplicados=resumo.aplicados,
        pendentes=resumo.pendentes,
        motivos_pendencia=resumo.motivos_pendencia,
    )


@router.get("/auditoria/{lancamento_id}", response_model=AuditoriaRateioResponse)
def auditoria_rateio(
    lancamento_id: int,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditoriaRateioResponse:
    repo = SqlAlchemyAuditoriaRepository(db)
    memoria = repo.buscar(REFERENCIA_TIPO_RATEIO_LANCAMENTO, lancamento_id)
    if memoria is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem memória de cálculo para este lançamento.")
    return AuditoriaRateioResponse(memoria=memoria)
