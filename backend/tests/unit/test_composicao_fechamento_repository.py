from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain import entities
from app.infrastructure.db import models
from app.infrastructure.db.base import Base
from app.infrastructure.repositories.composicao_repository import SqlAlchemyComposicaoRepository
from app.infrastructure.repositories.fechamento_repository import SqlAlchemyFechamentoRepository

MES = date(2026, 6, 1)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _item(categoria=entities.CategoriaLancamento.FRETE, valor=Decimal("100")):
    return entities.ItemComposicao(
        categoria=categoria,
        valor_documentos=Decimal("0"),
        valor_contabilizado=valor,
        valor_rateado=Decimal("0"),
        percentual_rateio=None,
        diferenca=Decimal("0"),
    )


def test_composicao_cria_processo_minimo_quando_nao_sincronizado(db_session):
    repo = SqlAlchemyComposicaoRepository(db_session)
    composicao = entities.ComposicaoContabil(processo_codigo="GOC99999", mes_referencia=MES, itens=[_item()])

    repo.salvar(composicao)

    processo = db_session.scalar(select(models.Processo).where(models.Processo.codigo == "GOC99999"))
    assert processo is not None
    assert processo.empresa.codigo == "GOC"
    itens = repo.listar("GOC99999", MES)
    assert len(itens) == 1
    assert itens[0].valor_contabilizado == Decimal("100")


def test_composicao_substitui_itens_antigos_ao_resalvar(db_session):
    repo = SqlAlchemyComposicaoRepository(db_session)
    repo.salvar(entities.ComposicaoContabil(processo_codigo="GOC25129", mes_referencia=MES, itens=[_item(valor=Decimal("100"))]))
    repo.salvar(
        entities.ComposicaoContabil(
            processo_codigo="GOC25129",
            mes_referencia=MES,
            itens=[_item(valor=Decimal("200")), _item(entities.CategoriaLancamento.HONORARIOS, Decimal("50"))],
        )
    )

    itens = repo.listar("GOC25129", MES)
    assert len(itens) == 2
    todos_itens_no_banco = db_session.scalars(select(models.ComposicaoContabil)).all()
    assert len(todos_itens_no_banco) == 2  # não duplicou a primeira rodada


def test_fechamento_salvar_e_buscar(db_session):
    repo = SqlAlchemyFechamentoRepository(db_session)
    resultado = entities.ResultadoFechamento(
        processo_codigo="GOC25129",
        mes_referencia=MES,
        status=entities.StatusFechamento.PENDENTE,
        saldo_final=Decimal("123.45"),
        variacao_cambial=None,
        motivos_pendencia=["Saldo não fechou"],
    )
    repo.salvar(resultado)

    encontrado = repo.buscar("GOC25129", MES)
    assert encontrado.status == entities.StatusFechamento.PENDENTE
    assert encontrado.saldo_final == Decimal("123.45")
    assert encontrado.motivos_pendencia == ["Saldo não fechou"]


def test_fechamento_upsert_atualiza_status_sem_duplicar(db_session):
    repo = SqlAlchemyFechamentoRepository(db_session)
    base = entities.ResultadoFechamento(
        processo_codigo="GOC25129", mes_referencia=MES, status=entities.StatusFechamento.PENDENTE,
        saldo_final=Decimal("50"), variacao_cambial=None, motivos_pendencia=["x"],
    )
    repo.salvar(base)
    base.status = entities.StatusFechamento.FECHADO
    base.saldo_final = Decimal("0")
    base.motivos_pendencia = []
    repo.salvar(base)

    encontrado = repo.buscar("GOC25129", MES)
    assert encontrado.status == entities.StatusFechamento.FECHADO
    todas_linhas = db_session.scalars(select(models.Fechamento)).all()
    assert len(todas_linhas) == 1


def test_listar_por_mes(db_session):
    repo = SqlAlchemyFechamentoRepository(db_session)
    repo.salvar(
        entities.ResultadoFechamento(
            processo_codigo="GOC25129", mes_referencia=MES, status=entities.StatusFechamento.FECHADO,
            saldo_final=Decimal("0"), variacao_cambial=None, motivos_pendencia=[],
        )
    )
    repo.salvar(
        entities.ResultadoFechamento(
            processo_codigo="BBI25167", mes_referencia=MES, status=entities.StatusFechamento.BLOQUEADO,
            saldo_final=Decimal("0"), variacao_cambial=None, motivos_pendencia=["sem DI"],
        )
    )

    resultados = repo.listar_por_mes(MES)
    assert {r.processo_codigo for r in resultados} == {"GOC25129", "BBI25167"}
