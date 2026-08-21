from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.razao import ResumoImportacaoRazaoResponse
from app.application.use_cases.importar_razao import ImportarRazaoUseCase
from app.infrastructure.classification.lancamento_classifier import (
    KeywordLancamentoClassifier,
    LancamentoClassifierComAprendizado,
)
from app.infrastructure.db.session import get_db
from app.infrastructure.razao.parser import RazaoCsvParser
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository
from app.infrastructure.repositories.regras_aprendidas_repository import SqlAlchemyRegrasAprendidasRepository

router = APIRouter(prefix="/razao", tags=["razao"])


@router.post("/upload", response_model=ResumoImportacaoRazaoResponse)
async def upload_razao(
    arquivo: UploadFile,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumoImportacaoRazaoResponse:
    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio")

    use_case = ImportarRazaoUseCase(
        parser=RazaoCsvParser(),
        classifier=LancamentoClassifierComAprendizado(
            KeywordLancamentoClassifier(), SqlAlchemyRegrasAprendidasRepository(db)
        ),
        repo=SqlAlchemyRazaoRepository(db),
    )
    try:
        resumo = use_case.executar(conteudo, arquivo.filename or "razao.csv")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if resumo.total_lancamentos == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum lançamento reconhecido no arquivo - confirme o formato do Razão.",
        )

    return ResumoImportacaoRazaoResponse(
        mes_referencia=resumo.mes_referencia,
        total_lancamentos=resumo.total_lancamentos,
        total_valor_debito=float(resumo.total_valor_debito),
        total_valor_credito=float(resumo.total_valor_credito),
        processos_citados=resumo.processos_citados,
        lancamentos_sem_processo=resumo.lancamentos_sem_processo,
        lancamentos_multi_processo=resumo.lancamentos_multi_processo,
        por_categoria=resumo.por_categoria,
    )
