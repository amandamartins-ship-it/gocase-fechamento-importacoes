from datetime import date
from decimal import Decimal

from app.domain.entities import CategoriaLancamento, ItemComposicao, ResultadoFechamento, StatusFechamento
from app.domain.indicadores import calcular_indicadores

MES = date(2026, 6, 1)


def _item(valor=Decimal("100"), rateado=Decimal("0")):
    return ItemComposicao(
        categoria=CategoriaLancamento.FRETE,
        valor_documentos=Decimal("0"),
        valor_contabilizado=valor,
        valor_rateado=rateado,
        percentual_rateio=None,
        diferenca=Decimal("0"),
    )


def _fechamento(codigo, status, saldo=Decimal("0"), variacao=None):
    return ResultadoFechamento(
        processo_codigo=codigo, mes_referencia=MES, status=status, saldo_final=saldo,
        variacao_cambial=variacao, motivos_pendencia=[],
    )


def test_lista_vazia_nao_divide_por_zero():
    ind = calcular_indicadores([])
    assert ind.total_processos == 0
    assert ind.percentual_automacao == Decimal("0")
    assert ind.indice_qualidade_fechamento == Decimal("0")


def test_conta_status_corretamente():
    itens = [
        (_fechamento("A", StatusFechamento.FECHADO), [_item(Decimal("100"))]),
        (_fechamento("B", StatusFechamento.PENDENTE, saldo=Decimal("30")), [_item(Decimal("200"))]),
        (_fechamento("C", StatusFechamento.BLOQUEADO), [_item(Decimal("50"))]),
    ]
    ind = calcular_indicadores(itens)

    assert ind.total_processos == 3
    assert ind.processos_fechados == 1
    assert ind.processos_pendentes == 1
    assert ind.processos_bloqueados == 1
    assert ind.valor_pendente == Decimal("30")
    assert ind.valor_total_contabilizado == Decimal("350")


def test_percentual_automacao_e_indice_qualidade():
    # 2 fechados, 1 pendente, 1 bloqueado, total 4
    itens = [
        (_fechamento("A", StatusFechamento.FECHADO), [_item()]),
        (_fechamento("B", StatusFechamento.FECHADO), [_item()]),
        (_fechamento("C", StatusFechamento.PENDENTE), [_item()]),
        (_fechamento("D", StatusFechamento.BLOQUEADO), [_item()]),
    ]
    ind = calcular_indicadores(itens)

    assert ind.percentual_automacao == Decimal("50")  # 2/4 * 100
    # (2 + 1*0.5) / 4 * 100 = 62.5
    assert ind.indice_qualidade_fechamento == Decimal("62.5")


def test_variacao_cambial_so_soma_quando_presente():
    itens = [
        (_fechamento("A", StatusFechamento.FECHADO, variacao=Decimal("15")), [_item()]),
        (_fechamento("B", StatusFechamento.FECHADO, variacao=None), [_item()]),
    ]
    ind = calcular_indicadores(itens)
    assert ind.total_variacao_cambial == Decimal("15")


def test_valor_rateado_soma_dos_itens():
    itens = [(_fechamento("A", StatusFechamento.FECHADO), [_item(Decimal("100"), rateado=Decimal("40"))])]
    ind = calcular_indicadores(itens)
    assert ind.valor_total_rateado == Decimal("40")
