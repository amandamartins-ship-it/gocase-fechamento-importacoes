from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.fechamento import (
    FechamentoProcessoResponse,
    ItemComposicaoResponse,
    ResumoProcessamentoFechamentoResponse,
)
from app.application.use_cases.gerar_linhas_rateio import GerarLinhasRazaoRateadoUseCase
from app.application.use_cases.montar_composicao import MontarComposicaoUseCase
from app.application.use_cases.processar_fechamento import (
    ProcessarFechamentoMesUseCase,
    ProcessarFechamentoProcessoUseCase,
)
from app.application.use_cases.validar_fechamento import ValidarFechamentoUseCase
from app.core.config import get_settings
from app.domain.entities import ItemComposicao, ResultadoFechamento, StatusFechamento
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.composicao_repository import SqlAlchemyComposicaoRepository
from app.infrastructure.repositories.fechamento_repository import SqlAlchemyFechamentoRepository
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository
from app.infrastructure.repositories.rateio_repository import SqlAlchemyAuditoriaRepository
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository
from app.infrastructure.xlsx.exportador import construir_processos_fechados, construir_razao_atualizado

router = APIRouter(prefix="/fechamento", tags=["fechamento"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _montar_processar_processo_use_case(db: Session) -> ProcessarFechamentoProcessoUseCase:
    settings = get_settings()
    return ProcessarFechamentoProcessoUseCase(
        processo_repo=SqlAlchemyProcessoRepository(db),
        montar_composicao=MontarComposicaoUseCase(
            razao_repo=SqlAlchemyRazaoRepository(db), auditoria_repo=SqlAlchemyAuditoriaRepository(db)
        ),
        validar_fechamento=ValidarFechamentoUseCase(Decimal(str(settings.tolerancia_variacao_cambial))),
        composicao_repo=SqlAlchemyComposicaoRepository(db),
        fechamento_repo=SqlAlchemyFechamentoRepository(db),
    )


def _item_response(item: ItemComposicao) -> ItemComposicaoResponse:
    return ItemComposicaoResponse(
        categoria=str(item.categoria),
        valor_documentos=float(item.valor_documentos),
        valor_contabilizado=float(item.valor_contabilizado),
        valor_rateado=float(item.valor_rateado),
        percentual_rateio=float(item.percentual_rateio) if item.percentual_rateio is not None else None,
        diferenca=float(item.diferenca),
    )


def _fechamento_response(
    resultado: ResultadoFechamento, composicao: list[ItemComposicao]
) -> FechamentoProcessoResponse:
    return FechamentoProcessoResponse(
        processo_codigo=resultado.processo_codigo,
        mes_referencia=resultado.mes_referencia,
        status=str(resultado.status),
        saldo_final=float(resultado.saldo_final),
        variacao_cambial=float(resultado.variacao_cambial) if resultado.variacao_cambial is not None else None,
        motivos_pendencia=resultado.motivos_pendencia,
        composicao=[_item_response(item) for item in composicao],
    )


@router.post("/processar", response_model=ResumoProcessamentoFechamentoResponse)
def processar_fechamento_mes(
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumoProcessamentoFechamentoResponse:
    mes = mes_referencia.replace(day=1)
    use_case = ProcessarFechamentoMesUseCase(
        processo_repo=SqlAlchemyProcessoRepository(db),
        razao_repo=SqlAlchemyRazaoRepository(db),
        processar_processo=_montar_processar_processo_use_case(db),
    )
    resumo = use_case.executar(mes)

    composicao_repo = SqlAlchemyComposicaoRepository(db)
    resultados_response = [
        _fechamento_response(resultado, composicao_repo.listar(resultado.processo_codigo, mes))
        for resultado in resumo.resultados
    ]

    ind = resumo.indicadores
    return ResumoProcessamentoFechamentoResponse(
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
        resultados=resultados_response,
    )


@router.get("/exportar/razao-atualizado.xlsx")
def exportar_razao_atualizado(
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Todas as linhas do mês já rateadas por processo, com o status de
    fechamento calculado - equivalente à aba 'Base' de 'Importações em
    Andamento', mas gerado automaticamente."""
    mes = mes_referencia.replace(day=1)
    use_case = GerarLinhasRazaoRateadoUseCase(
        razao_repo=SqlAlchemyRazaoRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaRepository(db),
        fechamento_repo=SqlAlchemyFechamentoRepository(db),
    )
    conteudo = construir_razao_atualizado(use_case.executar(mes))
    nome_arquivo = f"Razao_Atualizado_{mes.strftime('%m%Y')}.xlsx"
    return Response(
        content=conteudo,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/exportar/processos-fechados.xlsx")
def exportar_processos_fechados(
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Uma aba por processo com status Fechado no mês, com as linhas rateadas,
    a linha de totais e o 'Saldo processo' - a mesma memória de cálculo que a
    equipe hoje monta copiando e colando manualmente em 'Processos Fechados'."""
    mes = mes_referencia.replace(day=1)
    use_case = GerarLinhasRazaoRateadoUseCase(
        razao_repo=SqlAlchemyRazaoRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaRepository(db),
        fechamento_repo=SqlAlchemyFechamentoRepository(db),
    )
    todas_as_linhas = use_case.executar(mes)

    linhas_por_processo: dict[str, list] = {}
    status_fechado = str(StatusFechamento.FECHADO)
    for linha in todas_as_linhas:
        if linha.status != status_fechado:
            continue
        linhas_por_processo.setdefault(linha.processo_full, []).append(linha)

    conteudo = construir_processos_fechados(linhas_por_processo)
    nome_arquivo = f"Processos_Fechados_{mes.strftime('%m%Y')}.xlsx"
    return Response(
        content=conteudo,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/{processo_codigo}", response_model=FechamentoProcessoResponse)
def obter_fechamento_processo(
    processo_codigo: str,
    mes_referencia: date,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FechamentoProcessoResponse:
    mes = mes_referencia.replace(day=1)
    fechamento_repo = SqlAlchemyFechamentoRepository(db)
    resultado = fechamento_repo.buscar(processo_codigo, mes)
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum fechamento processado para este processo/mês ainda.",
        )
    composicao = SqlAlchemyComposicaoRepository(db).listar(processo_codigo, mes)
    return _fechamento_response(resultado, composicao)
