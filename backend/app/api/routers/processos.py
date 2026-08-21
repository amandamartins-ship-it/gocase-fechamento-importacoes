from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.processos import (
    DashboardIndicadoresResponse,
    ExtracaoValoresResponse,
    LancamentoResumoResponse,
    LinhaRateadaResponse,
    LinhasRateadasProcessoResponse,
    ProcessoResumoResponse,
)
from app.application.use_cases.extrair_valores_documentos import ExtrairValoresDocumentosUseCase
from app.application.use_cases.gerar_linhas_rateio import GerarLinhasRazaoRateadoUseCase
from app.domain.indicadores import calcular_indicadores
from app.infrastructure.classification.keyword_classifier import KeywordDocumentClassifier
from app.infrastructure.db import models
from app.infrastructure.db.session import get_db
from app.infrastructure.drive.client import DriveAuthError, GoogleDriveRepository
from app.infrastructure.repositories.composicao_repository import SqlAlchemyComposicaoRepository
from app.infrastructure.repositories.fechamento_repository import SqlAlchemyFechamentoRepository
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository
from app.infrastructure.repositories.rateio_repository import SqlAlchemyAuditoriaRepository
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository

router = APIRouter(prefix="/processos", tags=["processos"])


def _ultimo_mes_com_fechamento(db: Session) -> date | None:
    return db.scalar(select(func.max(models.Fechamento.mes_referencia)))


@router.get("", response_model=list[ProcessoResumoResponse])
def listar_processos(
    mes_referencia: date | None = None,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProcessoResumoResponse]:
    processos = SqlAlchemyProcessoRepository(db).listar()
    mes = mes_referencia.replace(day=1) if mes_referencia else _ultimo_mes_com_fechamento(db)
    fechamento_repo = SqlAlchemyFechamentoRepository(db)

    resultado = []
    for processo in processos:
        fechamento = fechamento_repo.buscar(processo.codigo, mes) if mes else None
        resultado.append(
            ProcessoResumoResponse(
                codigo=processo.codigo,
                empresa_codigo=processo.empresa_codigo,
                descricao=processo.descricao,
                fornecedor=processo.fornecedor,
                status=str(fechamento.status) if fechamento else None,
                saldo_final=float(fechamento.saldo_final) if fechamento else None,
            )
        )
    return resultado


@router.get("/dashboard", response_model=DashboardIndicadoresResponse)
def dashboard(
    mes_referencia: date | None = None,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardIndicadoresResponse:
    mes = mes_referencia.replace(day=1) if mes_referencia else _ultimo_mes_com_fechamento(db)
    if mes is None:
        return DashboardIndicadoresResponse(
            total_processos=0,
            processos_fechados=0,
            processos_pendentes=0,
            processos_bloqueados=0,
            valor_total_contabilizado=0,
            valor_total_rateado=0,
            valor_pendente=0,
            total_variacao_cambial=0,
            percentual_automacao=0,
            indice_qualidade_fechamento=0,
        )

    fechamento_repo = SqlAlchemyFechamentoRepository(db)
    composicao_repo = SqlAlchemyComposicaoRepository(db)
    resultados = fechamento_repo.listar_por_mes(mes)
    ind = calcular_indicadores([(r, composicao_repo.listar(r.processo_codigo, mes)) for r in resultados])
    return DashboardIndicadoresResponse(
        total_processos=ind.total_processos,
        processos_fechados=ind.processos_fechados,
        processos_pendentes=ind.processos_pendentes,
        processos_bloqueados=ind.processos_bloqueados,
        valor_total_contabilizado=float(ind.valor_total_contabilizado),
        valor_total_rateado=float(ind.valor_total_rateado),
        valor_pendente=float(ind.valor_pendente),
        total_variacao_cambial=float(ind.total_variacao_cambial),
        percentual_automacao=float(ind.percentual_automacao),
        indice_qualidade_fechamento=float(ind.indice_qualidade_fechamento),
    )


@router.get("/{codigo}/lancamentos", response_model=list[LancamentoResumoResponse])
def listar_lancamentos_do_processo(
    codigo: str,
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LancamentoResumoResponse]:
    lancamentos = SqlAlchemyRazaoRepository(db).listar_por_processo(codigo, mes_referencia.replace(day=1))
    return [
        LancamentoResumoResponse(
            id=l.id,
            historico=l.historico,
            categoria=str(l.categoria_classificada) if l.categoria_classificada else None,
            valor_debito=float(l.valor_debito),
            valor_credito=float(l.valor_credito),
            processos_codigos=l.processos_codigos,
            rateio_aplicado=l.rateio_aplicado,
        )
        for l in lancamentos
    ]


@router.get("/{codigo}/linhas-rateadas", response_model=LinhasRateadasProcessoResponse)
def linhas_rateadas_do_processo(
    codigo: str,
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LinhasRateadasProcessoResponse:
    """Linhas do processo já "explodidas" por participante e com valor
    rateado preenchido - o mesmo formato de 'Processos Fechados', pronto para
    conferência dentro do sistema (sem precisar copiar/colar no Excel)."""
    mes = mes_referencia.replace(day=1)
    use_case = GerarLinhasRazaoRateadoUseCase(
        razao_repo=SqlAlchemyRazaoRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaRepository(db),
        fechamento_repo=SqlAlchemyFechamentoRepository(db),
    )
    todas_as_linhas = use_case.executar(mes)
    linhas = [l for l in todas_as_linhas if l.processo_full == codigo]

    total_debito = sum((l.debito for l in linhas), Decimal("0"))
    total_credito = sum((l.credito for l in linhas), Decimal("0"))

    return LinhasRateadasProcessoResponse(
        linhas=[
            LinhaRateadaResponse(
                lancamento_id=l.lancamento_id,
                empresa=l.empresa,
                data=l.data,
                conta=l.conta,
                numero_contabil=l.numero_contabil,
                unidade=l.unidade,
                historico=l.historico,
                debito=float(l.debito),
                credito=float(l.credito),
                movimentacao=float(l.movimentacao),
                processo=l.processo,
                processo_full=l.processo_full,
                processo_controle_importacao=l.processo_controle_importacao,
                status=l.status,
            )
            for l in linhas
        ],
        total_debito=float(total_debito),
        total_credito=float(total_credito),
        saldo_processo=float(total_debito - total_credito),
    )


@router.post("/{codigo}/extrair-valores", response_model=ExtracaoValoresResponse)
def extrair_valores_documentos(
    codigo: str,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtracaoValoresResponse:
    """Lê de verdade cada documento ainda pendente da pasta FATURAMENTO FINAL
    deste processo (Fase 9) e grava o valor extraído - depois disso, a
    composição contábil (Fase 5) passa a mostrar 'valor_documentos'/'diferenca'
    reais em vez de zero."""
    drive_repo = GoogleDriveRepository(KeywordDocumentClassifier())
    use_case = ExtrairValoresDocumentosUseCase(
        processo_repo=SqlAlchemyProcessoRepository(db),
        drive_repo=drive_repo,
    )
    try:
        resultado = use_case.executar(codigo)
    except DriveAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ExtracaoValoresResponse(
        documentos_processados=resultado.documentos_processados,
        documentos_com_valor_encontrado=resultado.documentos_com_valor_encontrado,
    )
