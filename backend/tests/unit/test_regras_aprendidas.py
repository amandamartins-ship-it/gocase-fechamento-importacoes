from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.entities import DocumentoRef, TipoDocumento
from app.infrastructure.classification.keyword_classifier import (
    DocumentClassifierComAprendizado,
    KeywordDocumentClassifier,
)
from app.infrastructure.classification.lancamento_classifier import (
    KeywordLancamentoClassifier,
    LancamentoClassifierComAprendizado,
)
from app.infrastructure.db.base import Base
from app.infrastructure.repositories.regras_aprendidas_repository import SqlAlchemyRegrasAprendidasRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_regra_registrada_e_encontrada_por_substring(db_session):
    repo = SqlAlchemyRegrasAprendidasRepository(db_session)
    repo.registrar("classificacao", "TAXA XPTO", "Outras despesas", "sempre foi mal classificado", "amanda@gocase.com")

    assert repo.buscar_valor_corrigido("classificacao", "PAGAMENTO TAXA XPTO REF 123") == "Outras despesas"
    assert repo.buscar_valor_corrigido("classificacao", "algo completamente diferente") is None
    assert repo.buscar_valor_corrigido("documento", "TAXA XPTO") is None  # tipo errado, não vaza


def test_regra_mais_recente_vence_quando_ha_conflito(db_session):
    repo = SqlAlchemyRegrasAprendidasRepository(db_session)
    repo.registrar("classificacao", "FRETE ESPECIAL", "Frete", None, "amanda@gocase.com")
    repo.registrar("classificacao", "FRETE ESPECIAL", "Outras despesas", "correção da correção", "amanda@gocase.com")

    assert repo.buscar_valor_corrigido("classificacao", "PAGAMENTO FRETE ESPECIAL") == "Outras despesas"


def test_listar_filtra_por_tipo(db_session):
    repo = SqlAlchemyRegrasAprendidasRepository(db_session)
    repo.registrar("classificacao", "A", "Frete", None, "x")
    repo.registrar("documento", "B", str(TipoDocumento.DI), None, "x")

    assert len(repo.listar()) == 2
    assert len(repo.listar("documento")) == 1
    assert repo.listar("documento")[0]["padrao"] == "B"


def test_lancamento_classifier_com_aprendizado_tem_prioridade_sobre_dicionario(db_session):
    repo = SqlAlchemyRegrasAprendidasRepository(db_session)
    repo.registrar("classificacao", "TAXA ESPECIAL DO BANCO X", "Honorários", None, "amanda@gocase.com")

    classifier = LancamentoClassifierComAprendizado(KeywordLancamentoClassifier(), repo)

    # sem a regra aprendida, o dicionário estático classificaria como "Outras despesas"
    assert classifier.classificar("PAGAMENTO TAXA ESPECIAL DO BANCO X", None) == "Honorários"
    # sem correção aplicável, cai no dicionário estático normalmente
    assert classifier.classificar("PGTO FRETE INTERNACIONAL GOC25129", None) == "Frete"


def test_document_classifier_com_aprendizado_tem_prioridade_sobre_dicionario(db_session):
    repo = SqlAlchemyRegrasAprendidasRepository(db_session)
    repo.registrar("documento", "RELATORIO ESPECIAL", str(TipoDocumento.RELATORIO_ITENS), None, "amanda@gocase.com")

    classifier = DocumentClassifierComAprendizado(KeywordDocumentClassifier(), repo)
    ref = DocumentoRef(drive_file_id="x", nome_arquivo="RELATORIO ESPECIAL.pdf", caminho="x")

    # sem a regra, "RELATORIO ESPECIAL.pdf" não bate com nenhuma regra estática -> OUTRO
    assert classifier.classificar(ref) == str(TipoDocumento.RELATORIO_ITENS)

    ref_sem_regra = DocumentoRef(drive_file_id="y", nome_arquivo="DI - 123.pdf", caminho="y")
    assert classifier.classificar(ref_sem_regra) == str(TipoDocumento.DI)
