import pytest

from app.domain.entities import CategoriaLancamento
from app.infrastructure.classification.lancamento_dictionaries import classificar_historico
from app.infrastructure.util.texto import normalizar_texto

CASOS = [
    ("PGTO FRETE INTERNACIONAL PROCESSO GOC25129", CategoriaLancamento.FRETE),
    ("ARMAZENAGEM PORTO DE SANTOS", CategoriaLancamento.ARMAZENAGEM),
    ("HONORARIOS DESPACHANTE ADUANEIRO", CategoriaLancamento.HONORARIOS),
    ("AFRMM PROCESSO BBI25167", CategoriaLancamento.AFRMM),
    ("SEGURO TRANSPORTE INTERNACIONAL", CategoriaLancamento.SEGURO),
    ("CAPATAZIA TERMINAL", CategoriaLancamento.CAPATAZIA),
    ("IOF SOBRE CAMBIO", CategoriaLancamento.IOF),
    ("PAGTO NUMERARIO GOC25129", CategoriaLancamento.NUMERARIO),
    ("REEMBOLSO DE DESPESAS TRADING", CategoriaLancamento.REEMBOLSO),
    ("LANCAMENTO NOTA FISCAL DE ENTRADA GOC25129", CategoriaLancamento.NF_ENTRADA),
    ("AJUSTE DE VARIACAO CAMBIAL", CategoriaLancamento.VARIACAO_CAMBIAL),
    ("TARIFA BANCARIA MENSAL", CategoriaLancamento.OUTRAS_DESPESAS),
    ("COMPRA DE MERCADORIA IMPORTADA", CategoriaLancamento.MERCADORIA),
]


@pytest.mark.parametrize("historico,esperado", CASOS)
def test_classificar_historico(historico, esperado):
    assert classificar_historico(normalizar_texto(historico)) == esperado


def test_afrmm_nao_e_confundido_com_frete():
    # "AFRMM" contém a sequencia de letras usada por "frete" só se o regex for descuidado -
    # garante que a regra mais específica (AFRMM) vem antes da genérica (frete).
    assert classificar_historico(normalizar_texto("AFRMM PROCESSO GOC25129")) == CategoriaLancamento.AFRMM
