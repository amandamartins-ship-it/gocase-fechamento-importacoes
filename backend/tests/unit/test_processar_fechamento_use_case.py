"""Integração de ponta a ponta (sem HTTP) do motor de fechamento: sincroniza
processos (como a Fase 2 faria), importa lançamentos (Fase 3), simula um
rateio já aplicado (Fase 4) e roda o fechamento do mês inteiro (Fase 5) contra
um Postgres real seria o ideal, mas SQLite em memória cobre toda a lógica de
persistência/orquestração sem precisar de Docker."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.application.use_cases.montar_composicao import MontarComposicaoUseCase
from app.application.use_cases.processar_fechamento import (
    ProcessarFechamentoMesUseCase,
    ProcessarFechamentoProcessoUseCase,
)
from app.application.use_cases.validar_fechamento import ValidarFechamentoUseCase
from app.domain import entities
from app.infrastructure.db.base import Base
from app.infrastructure.repositories.composicao_repository import SqlAlchemyComposicaoRepository
from app.infrastructure.repositories.fechamento_repository import SqlAlchemyFechamentoRepository
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository
from app.infrastructure.repositories.rateio_repository import SqlAlchemyAuditoriaRepository
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository

MES = date(2026, 6, 1)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _processo_completo(codigo: str, empresa: str) -> entities.Processo:
    embarque = entities.Embarque(codigo=f"{codigo}.1", drive_folder_id="f")
    for tipo in (entities.TipoDocumento.DI, entities.TipoDocumento.INVOICE_CI, entities.TipoDocumento.NOTA_FISCAL):
        embarque.documentos.append(
            entities.Documento(
                ref=entities.DocumentoRef(drive_file_id=f"{codigo}-{tipo}", nome_arquivo="x.pdf", caminho="x"),
                tipo=tipo,
            )
        )
    processo = entities.Processo(codigo=codigo, empresa_codigo=empresa)
    processo.embarques = [embarque]
    return processo


def _montar_use_case_processo(db: Session) -> ProcessarFechamentoProcessoUseCase:
    return ProcessarFechamentoProcessoUseCase(
        processo_repo=SqlAlchemyProcessoRepository(db),
        montar_composicao=MontarComposicaoUseCase(
            razao_repo=SqlAlchemyRazaoRepository(db), auditoria_repo=SqlAlchemyAuditoriaRepository(db)
        ),
        validar_fechamento=ValidarFechamentoUseCase(Decimal("0.02")),
        composicao_repo=SqlAlchemyComposicaoRepository(db),
        fechamento_repo=SqlAlchemyFechamentoRepository(db),
    )


def test_processamento_do_mes_classifica_fechado_pendente_bloqueado_corretamente(db_session):
    processo_repo = SqlAlchemyProcessoRepository(db_session)
    razao_repo = SqlAlchemyRazaoRepository(db_session)

    # GOC25129: documentos completos, lançamentos que se anulam -> deve fechar
    processo_repo.salvar(_processo_completo("GOC25129", "GOC"))
    # BBI25167: nunca sincronizado no Drive -> Bloqueado (documentos ausentes)
    # GOC99999: documentos completos, mas tem um lançamento multi-processo sem rateio aplicado -> Pendente
    processo_repo.salvar(_processo_completo("GOC99999", "GOC"))

    # cada upload do Razão é a "foto" inteira do mês (ver SqlAlchemyRazaoRepository.salvar_lote) -
    # por isso os 4 lançamentos de todos os processos vão num único lote.
    razao_repo.salvar_lote(
        [
            entities.LancamentoRazao(
                mes_referencia=MES, historico="FRETE GOC25129", valor_debito=Decimal("100"), valor_credito=Decimal("0"),
                processos_codigos=["GOC25129"], categoria_classificada=entities.CategoriaLancamento.FRETE,
            ),
            entities.LancamentoRazao(
                mes_referencia=MES, historico="REEMBOLSO GOC25129", valor_debito=Decimal("0"), valor_credito=Decimal("100"),
                processos_codigos=["GOC25129"], categoria_classificada=entities.CategoriaLancamento.REEMBOLSO,
            ),
            entities.LancamentoRazao(
                mes_referencia=MES, historico="FRETE BBI25167", valor_debito=Decimal("50"), valor_credito=Decimal("0"),
                processos_codigos=["BBI25167"], categoria_classificada=entities.CategoriaLancamento.FRETE,
            ),
            entities.LancamentoRazao(
                mes_referencia=MES, historico="NUMERARIO GOC99999 E GOC88888", valor_debito=Decimal("300"),
                valor_credito=Decimal("0"), processos_codigos=["GOC99999", "GOC88888"],
                categoria_classificada=entities.CategoriaLancamento.NUMERARIO,
            ),
        ]
    )

    use_case_mes = ProcessarFechamentoMesUseCase(
        processo_repo=processo_repo, razao_repo=razao_repo, processar_processo=_montar_use_case_processo(db_session)
    )
    resumo = use_case_mes.executar(MES)

    status_por_processo = {r.processo_codigo: r.status for r in resumo.resultados}
    assert status_por_processo["GOC25129"] == entities.StatusFechamento.FECHADO
    assert status_por_processo["BBI25167"] == entities.StatusFechamento.BLOQUEADO
    assert status_por_processo["GOC99999"] == entities.StatusFechamento.PENDENTE
    # GOC88888 também é citado no lançamento multi-processo, mas não tem seus próprios
    # lançamentos "principais" - ainda assim entra na lista (união razão+drive) e fica Bloqueado
    # (sem documentos conhecidos), o que é o comportamento correto (nunca fica de fora silenciosamente).
    assert "GOC88888" in status_por_processo

    ind = resumo.indicadores
    assert ind.total_processos == 4
    assert ind.processos_fechados == 1
    assert ind.processos_bloqueados == 2
    assert ind.processos_pendentes == 1

    # persistiu de verdade - buscar via o repositório confirma
    fechamento_repo = SqlAlchemyFechamentoRepository(db_session)
    assert fechamento_repo.buscar("GOC25129", MES).status == entities.StatusFechamento.FECHADO

    composicao_repo = SqlAlchemyComposicaoRepository(db_session)
    itens_goc25129 = composicao_repo.listar("GOC25129", MES)
    categorias = {item.categoria for item in itens_goc25129}
    assert entities.CategoriaLancamento.FRETE in categorias
    assert entities.CategoriaLancamento.REEMBOLSO in categorias
