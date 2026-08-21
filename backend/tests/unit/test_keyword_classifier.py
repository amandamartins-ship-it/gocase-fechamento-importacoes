"""Regressão do classificador de documentos contra nomes reais encontrados no
Drive (processos GOC25129, GOC25191 - serviço, BBI25167 - múltiplos embarques),
para não depender de acesso ao Drive/Docker para validar a heurística."""

import pytest

from app.domain.entities import TipoDocumento
from app.infrastructure.classification.dictionaries import classificar_por_nome
from app.infrastructure.classification.keyword_classifier import pasta_deve_ser_ignorada

CASOS_GERAL = [
    ("DI - 26 0223149-4.pdf", TipoDocumento.DI),
    ("PROTOCOLO DI.pdf", TipoDocumento.PROTOCOLO_DI),
    ("GOC25129.1 - PL.pdf", TipoDocumento.PACKING_LIST),
    ("GOC25129.1 - CI.pdf", TipoDocumento.INVOICE_CI),
    ("PI - BBI25167 - SANFENG.pdf", TipoDocumento.INVOICE_CI),
    ("BBI25167-PI-SANFENG updated 01.xlsx", TipoDocumento.INVOICE_CI),
    ("BBI25167-CI-SANFENG.pdf", TipoDocumento.INVOICE_CI),
    ("GLME - GO.pdf", TipoDocumento.GLME),
    ("HAWB.pdf", TipoDocumento.AWB_HAWB),
    ("OHAWB - SA260509081.pdf", TipoDocumento.AWB_HAWB),
    ("DRAFT HBL - BCCANSSZ01336 (updated 01) .pdf", TipoDocumento.AWB_HAWB),
    ("NF 5926073 PROCESSO GOC25129.1.pdf", TipoDocumento.NOTA_FISCAL),
    ("NF 10634 PROCESSO BBI25167.1.xml", TipoDocumento.XML_NFE),
    ("2602231494.xml", TipoDocumento.XML_NFE),
    ("NUMERARIO GOC25129.1.pdf", TipoDocumento.NUMERARIO),
    ("NUMERÁRIO - DUIMP - CAI26002364.pdf", TipoDocumento.NUMERARIO),
    ("ICMS.pdf", TipoDocumento.ICMS),
    ("RASCUNHO DE NOTA FISCAL DE ENTRADA.pdf", TipoDocumento.RASCUNHO_NF_ENTRADA),
    ("COMPROVANTE DE IMPORTAÇÃO.pdf", TipoDocumento.COMPROVANTE_IMPORTACAO),
    ("RELATÓRIO DE ITENS.pdf", TipoDocumento.RELATORIO_ITENS),
    ("INSTRUÇÃO DE DESEMBARAÇO - GOC25129.1.xlsx", TipoDocumento.INSTRUCAO_DESEMBARACO),
    ("DUIMP DESEMBARAÇADA - 26BR0000873760-7.pdf", TipoDocumento.DI),
    ("DRAFT DUIMP.pdf", TipoDocumento.DI),
    ("EXTRATO DUIMP - 26BR0000873760-7.pdf", TipoDocumento.DI),
    ("I-AER-0550-26-ESPELHO NF.pdf", TipoDocumento.NOTA_FISCAL),
    # documentos sem regra específica devem cair em OUTRO, nunca em um chute.
    ("SWIFT (100%) - CC 552151740 - GOC25129 - NEWCOM.pdf", TipoDocumento.OUTRO),
    ("FOTO CARGA COLETA.png", TipoDocumento.OUTRO),
    ("Bank Details - PrintFactory.pdf", TipoDocumento.OUTRO),
    ("PROPOSTA COMERCIAL WMFQ261419.pdf", TipoDocumento.OUTRO),
]

CASOS_FATURAMENTO_FINAL_WMF = [
    ("1 - FRETE INTERNACIONAL.pdf", TipoDocumento.FRETE_INTERNACIONAL),
    ("2 - ICMS.pdf", TipoDocumento.ICMS),
    ("3 - ARMAZENAGEM.pdf", TipoDocumento.ARMAZENAGEM),
    ("4 - FRETE ENTREGA.pdf", TipoDocumento.FRETE_ENTREGA),
    ("5 - HONORÁRIOS.pdf", TipoDocumento.HONORARIOS),
    ("6 - NUMERÁRIO.pdf", TipoDocumento.NUMERARIO),
    ("7 - PRESTAÇÃO DE CONTAS.pdf", TipoDocumento.PRESTACAO_CONTAS),
    ("8 - DEVOLUÇÃO DO SALDO.pdf", TipoDocumento.DEVOLUCAO_SALDO),
]

CASOS_FATURAMENTO_FINAL_CODELI_AMBIGUOS = [
    # siglas específicas da trading (CODELI) sem categoria de despesa clara -
    # devem ficar OUTRO (pendência explícita depois) em vez de um chute.
    "I-AER-0550-26-ND.pdf",
    "I-AER-0550-26-NF.pdf",
    "I-AER-0550-26-REC.pdf",
    "DEV SALDO BB IND COM I-AER-0550-26 - 6687,86.pdf",
]


@pytest.mark.parametrize("nome_arquivo,esperado", CASOS_GERAL)
def test_classificacao_geral(nome_arquivo, esperado):
    caminho = f"Importações/2026/BB INDUSTRIA/BBI25167 - Produto/BBI25167.1 - Ref/{nome_arquivo}"
    assert classificar_por_nome(nome_arquivo, caminho) == esperado


@pytest.mark.parametrize("nome_arquivo,esperado", CASOS_FATURAMENTO_FINAL_WMF)
def test_classificacao_faturamento_final_wmf(nome_arquivo, esperado):
    caminho = f"Importações/.../GOC25129.1 - WMFIA261430/WMF - FATURAMENTO FINAL ( GOC25129.1)/{nome_arquivo}"
    assert classificar_por_nome(nome_arquivo, caminho) == esperado


def test_devolucao_saldo_codeli_reconhecida_apesar_do_nome_livre():
    nome = "DEV SALDO BB IND COM I-AER-0550-26 - 6687,86.pdf"
    caminho = f"Importações/.../BBI25167.1 - CAI26002364 (Aéreo)/CODELI - FATURAMENTO FINAL (BBI25167.1)/{nome}"
    assert classificar_por_nome(nome, caminho) == TipoDocumento.DEVOLUCAO_SALDO


@pytest.mark.parametrize("nome_arquivo", CASOS_FATURAMENTO_FINAL_CODELI_AMBIGUOS[:3])
def test_faturamento_final_ambiguo_vira_outro_nao_chute(nome_arquivo):
    caminho = f"Importações/.../BBI25167.1 - CAI26002364 (Aéreo)/CODELI - FATURAMENTO FINAL (BBI25167.1)/{nome_arquivo}"
    assert classificar_por_nome(nome_arquivo, caminho) == TipoDocumento.OUTRO


@pytest.mark.parametrize(
    "nome_pasta,esperado",
    [("OLD", True), ("old", True), (" Old ", True), ("OLDER STUFF", False), ("GOC25129.1 - WMFIA261430", False)],
)
def test_pasta_old_e_ignorada(nome_pasta, esperado):
    assert pasta_deve_ser_ignorada(nome_pasta) == esperado
