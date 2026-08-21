"""Valida a persistência da Fase 4 (razao_lancamentos.rateio_aplicado,
rateio_matriz, auditoria_calculo) usando SQLite em memória."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain import entities
from app.infrastructure.db import models
from app.infrastructure.db.base import Base
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository
from app.infrastructure.repositories.rateio_repository import SqlAlchemyAuditoriaRepository, SqlAlchemyRateioRepository
from app.infrastructure.repositories.razao_repository import SqlAlchemyRazaoRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_listar_multi_processo_pendentes_filtra_por_base_e_status(db_session):
    repo = SqlAlchemyRazaoRepository(db_session)
    repo.salvar_lote(
        [
            entities.LancamentoRazao(  # multi-processo real -> deve aparecer
                mes_referencia=date(2026, 6, 1),
                historico="A",
                valor_debito=Decimal("100"),
                valor_credito=Decimal("0"),
                processos_codigos=["GOC25129", "BBI25167"],
            ),
            entities.LancamentoRazao(  # mesmo processo com/sem sufixo de embarque -> NÃO é multi-processo
                mes_referencia=date(2026, 6, 1),
                historico="B",
                valor_debito=Decimal("50"),
                valor_credito=Decimal("0"),
                processos_codigos=["GOC25129", "GOC25129.1"],
            ),
            entities.LancamentoRazao(  # sem processo -> não é candidato
                mes_referencia=date(2026, 6, 1),
                historico="C",
                valor_debito=Decimal("10"),
                valor_credito=Decimal("0"),
                processos_codigos=[],
            ),
        ]
    )

    pendentes = repo.listar_multi_processo_pendentes(date(2026, 6, 1))
    assert len(pendentes) == 1
    assert pendentes[0].historico == "A"


def test_marcar_rateio_aplicado_remove_da_lista_de_pendentes(db_session):
    repo = SqlAlchemyRazaoRepository(db_session)
    repo.salvar_lote(
        [
            entities.LancamentoRazao(
                mes_referencia=date(2026, 6, 1),
                historico="A",
                valor_debito=Decimal("100"),
                valor_credito=Decimal("0"),
                processos_codigos=["GOC25129", "BBI25167"],
            )
        ]
    )
    lancamento_id = repo.listar_multi_processo_pendentes(date(2026, 6, 1))[0].id

    repo.marcar_rateio_aplicado(lancamento_id)

    assert repo.listar_multi_processo_pendentes(date(2026, 6, 1)) == []


def test_salvar_participante_upsert_por_processo_e_nf(db_session):
    processo_repo = SqlAlchemyProcessoRepository(db_session)
    processo_repo.salvar(entities.Processo(codigo="GOC25129", empresa_codigo="GOC"))

    rateio_repo = SqlAlchemyRateioRepository(db_session)
    rateio_repo.salvar_participante("GOC25129", "5876", 1000, 1500, Decimal("0.6667"), "Controle PIs")
    rateio_repo.salvar_participante("GOC25129", "5876", 1100, 1600, Decimal("0.6875"), "Controle PIs")  # reprocessamento

    linhas = db_session.scalars(select(models.RateioMatriz)).all()
    assert len(linhas) == 1  # upsert, não duplicou
    assert linhas[0].qtd_itens_processo == 1100
    assert linhas[0].qtd_itens_total_nf == 1600


def test_salvar_participante_ignora_processo_nao_sincronizado(db_session):
    rateio_repo = SqlAlchemyRateioRepository(db_session)
    rateio_repo.salvar_participante("GOC00000", "5876", 100, 200, Decimal("0.5"), "Controle PIs")

    assert db_session.scalars(select(models.RateioMatriz)).all() == []


def test_auditoria_registrar_e_buscar(db_session):
    repo = SqlAlchemyAuditoriaRepository(db_session)
    repo.registrar("rateio_lancamento", 42, {"nf_utilizada": "5876", "participantes": []})

    memoria = repo.buscar("rateio_lancamento", 42)
    assert memoria["nf_utilizada"] == "5876"
    assert repo.buscar("rateio_lancamento", 999) is None
