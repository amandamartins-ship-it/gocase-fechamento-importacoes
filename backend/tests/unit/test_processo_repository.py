"""Valida o upsert do SqlAlchemyProcessoRepository (substituição de embarques/
documentos a cada sincronização) usando SQLite em memória - sem precisar de
Postgres nem do Drive real."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain import entities
from app.infrastructure.db import models
from app.infrastructure.db.base import Base
from app.infrastructure.repositories.processo_repository import SqlAlchemyProcessoRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _processo_com_um_documento(nome_arquivo: str) -> entities.Processo:
    processo = entities.Processo(codigo="GOC25129", empresa_codigo="GOC", descricao="Bag Charm")
    embarque = entities.Embarque(codigo="GOC25129.1", drive_folder_id="folder-1")
    embarque.documentos.append(
        entities.Documento(
            ref=entities.DocumentoRef(drive_file_id="file-1", nome_arquivo=nome_arquivo, caminho="x"),
            tipo=entities.TipoDocumento.DI,
        )
    )
    processo.embarques.append(embarque)
    return processo


def test_salvar_cria_empresa_processo_embarque_documento(db_session):
    repo = SqlAlchemyProcessoRepository(db_session)
    salvo = repo.salvar(_processo_com_um_documento("DI - 123.pdf"))

    assert salvo.id is not None
    assert len(salvo.embarques) == 1
    assert salvo.embarques[0].documentos[0].ref.nome_arquivo == "DI - 123.pdf"

    empresa = db_session.scalar(select(models.Empresa).where(models.Empresa.codigo == "GOC"))
    assert empresa is not None and empresa.nome == "GO COMERCIO"


def test_resincronizar_substitui_embarques_sem_deixar_orfao(db_session):
    repo = SqlAlchemyProcessoRepository(db_session)
    repo.salvar(_processo_com_um_documento("DI - versao1.pdf"))

    # segunda sincronização: mesmo processo, documento diferente (simula o Drive mudando)
    salvo2 = repo.salvar(_processo_com_um_documento("DI - versao2.pdf"))

    assert len(salvo2.embarques) == 1
    assert salvo2.embarques[0].documentos[0].ref.nome_arquivo == "DI - versao2.pdf"

    # não deve sobrar nenhum Documento órfão da sincronização anterior
    todos_documentos = db_session.scalars(select(models.Documento)).all()
    assert len(todos_documentos) == 1
    todos_embarques = db_session.scalars(select(models.Embarque)).all()
    assert len(todos_embarques) == 1

    processos = db_session.scalars(select(models.Processo)).all()
    assert len(processos) == 1  # não duplicou o processo entre sincronizações


def test_resincronizar_preserva_valor_extraido_do_documento_ja_processado(db_session):
    repo = SqlAlchemyProcessoRepository(db_session)
    repo.salvar(_processo_com_um_documento("5 - HONORÁRIOS.pdf"))

    # simula a Fase 9 já ter extraído o valor deste documento
    doc_row = db_session.scalar(select(models.Documento).where(models.Documento.drive_file_id == "file-1"))
    doc_row.valor_extraido = Decimal("750.00")
    doc_row.status_leitura = str(entities.StatusLeituraDocumento.OK)
    db_session.commit()

    # novo sync do Drive - mesmo arquivo (mesmo drive_file_id), nome não muda
    salvo = repo.salvar(_processo_com_um_documento("5 - HONORÁRIOS.pdf"))

    doc_salvo = salvo.embarques[0].documentos[0]
    assert doc_salvo.valor_extraido == Decimal("750.00")
    assert doc_salvo.status_leitura == entities.StatusLeituraDocumento.OK


def test_atualizar_valor_documento_persiste_valor_e_status(db_session):
    repo = SqlAlchemyProcessoRepository(db_session)
    salvo = repo.salvar(_processo_com_um_documento("1 - FRETE INTERNACIONAL.pdf"))
    documento_id = salvo.embarques[0].documentos[0].id

    repo.atualizar_valor_documento(documento_id, Decimal("12291.35"), entities.StatusLeituraDocumento.OK)

    recarregado = repo.buscar_por_codigo("GOC25129")
    doc = recarregado.embarques[0].documentos[0]
    assert doc.valor_extraido == Decimal("12291.35")
    assert doc.status_leitura == entities.StatusLeituraDocumento.OK


def test_atualizar_valor_documento_inexistente_nao_lanca_excecao(db_session):
    repo = SqlAlchemyProcessoRepository(db_session)
    repo.atualizar_valor_documento(99999, Decimal("1.00"), entities.StatusLeituraDocumento.OK)


def test_resincronizar_remove_embarque_que_sumiu_do_drive(db_session):
    repo = SqlAlchemyProcessoRepository(db_session)
    processo = _processo_com_um_documento("DI - 123.pdf")
    processo.embarques.append(entities.Embarque(codigo="GOC25129.2", drive_folder_id="folder-2"))
    repo.salvar(processo)
    assert len(db_session.scalars(select(models.Embarque)).all()) == 2

    # segundo sync: só o embarque .1 continua existindo no Drive
    salvo = repo.salvar(_processo_com_um_documento("DI - 123.pdf"))

    assert len(salvo.embarques) == 1
    assert db_session.scalars(select(models.Embarque)).all().__len__() == 1
