"""Valida o parser do Razão contra o mesmo layout de export usado na
conciliação bancária (`;`, latin1, vírgula decimal - ver memória
gocase_reconciliation_pipeline) mais os campos específicos de importação
(código do processo dentro do histórico)."""

from datetime import date
from decimal import Decimal

from app.infrastructure.razao.parser import RazaoCsvParser
from app.infrastructure.razao.valores import parse_valor_brl

CABECALHO = (
    "Conta;Descricao da Conta;Data;Numero Contabil;Unidade;Historico;Contrapartida;"
    "Tipo;Documento;Terceiro;Nome Terceiro;Valor a Debito;Valor a Credito;Saldo;"
    "Indicador D/C;Centro de Resultado"
)

LINHAS = [
    # frete de um único processo
    "111301;Fretes a pagar;15/06/2026;411001;10001;PGTO FRETE INTERNACIONAL PROCESSO GOC25129;;D;NF001;123;"
    "Trading X;1.234,56;0,00;1.234,56;D;GO COMERCIO",
    # numerário citando 2 processos diferentes - candidato a rateio
    "111302;Numerario a pagar;16/06/2026;411002;10001;PAGTO NUMERARIO GOC25129 E BBI25167 RATEIO;;D;NF002;124;"
    "Trading X;500,00;0,00;500,00;D;GO COMERCIO",
    # lançamento sem nenhum código de processo
    "111303;Despesas gerais;17/06/2026;411003;10001;TARIFA BANCARIA MENSAL;;D;NF003;125;Banco;10,00;0,00;10,00;D;GO COMERCIO",
    # crédito com valor grande formato BR (milhar+decimal)
    "111304;Honorarios;18/06/2026;411004;10001;HONORARIOS DESPACHANTE GOC25129.1;;C;NF004;126;"
    "Despachante Y;0,00;12.345,67;12.345,67;C;GO COMERCIO",
]


def _csv_bytes() -> bytes:
    conteudo = "\n".join([CABECALHO, *LINHAS])
    return conteudo.encode("latin1")


def test_parse_reconhece_cabecalho_e_conta_lancamentos():
    lancamentos = RazaoCsvParser().parse(_csv_bytes(), "razao.csv")
    assert len(lancamentos) == 4


def test_parse_extrai_processo_unico_do_historico():
    lancamentos = RazaoCsvParser().parse(_csv_bytes(), "razao.csv")
    frete = lancamentos[0]
    assert frete.processos_codigos == ["GOC25129"]
    assert frete.valor_debito == Decimal("1234.56")


def test_parse_extrai_multiplos_processos_do_historico():
    lancamentos = RazaoCsvParser().parse(_csv_bytes(), "razao.csv")
    numerario = lancamentos[1]
    assert set(numerario.processos_codigos) == {"GOC25129", "BBI25167"}


def test_parse_lancamento_sem_processo_fica_com_lista_vazia():
    lancamentos = RazaoCsvParser().parse(_csv_bytes(), "razao.csv")
    tarifa = lancamentos[2]
    assert tarifa.processos_codigos == []


def test_parse_reconhece_codigo_com_sufixo_de_embarque():
    lancamentos = RazaoCsvParser().parse(_csv_bytes(), "razao.csv")
    honorarios = lancamentos[3]
    assert honorarios.processos_codigos == ["GOC25129.1"]
    assert honorarios.valor_credito == Decimal("12345.67")


def test_parse_normaliza_mes_referencia_para_o_mes_mais_frequente():
    lancamentos = RazaoCsvParser().parse(_csv_bytes(), "razao.csv")
    assert all(l.mes_referencia == date(2026, 6, 1) for l in lancamentos)


def test_parse_valor_brl_formatos():
    assert parse_valor_brl("1.234,56") == Decimal("1234.56")
    assert parse_valor_brl("0,00") == Decimal("0.00")
    assert parse_valor_brl("") == Decimal("0")
    assert parse_valor_brl(None) == Decimal("0")
    assert parse_valor_brl("1.024771826E7") == Decimal("1.024771826E7")
    assert parse_valor_brl("(150,00)") == Decimal("-150.00")
