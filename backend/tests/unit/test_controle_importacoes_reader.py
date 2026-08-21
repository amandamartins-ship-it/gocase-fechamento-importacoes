"""Valida o ControleImportacoesRateioBuilder contra uma planilha sintética que
reproduz o layout REAL confirmado em 2026-07-24 abrindo Controle de
Importações.xlsx de verdade: coluna A=Processo, G=Quantidade, AV=NF (índices
0, 6, 47) - inclusive o caso real confirmado de uma NF compartilhada por mais
de um processo (61 casos encontrados na planilha real nessa sessão)."""

import io
from decimal import Decimal

import openpyxl
import pytest

from app.infrastructure.xlsx.controle_importacoes import ControleImportacoesRateioBuilder


def _linha(processo, quantidade, nf):
    """Só as 3 colunas que importam são reais; o resto é preenchido com None
    até o índice 47 (NF), igual ao layout real da aba Controle PIs."""
    linha = [None] * 48
    linha[0] = processo
    linha[6] = quantidade
    linha[47] = nf
    return linha


def _montar_xlsx_bytes(linhas: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Controle PIs"
    ws.append(["col"] * 48)  # cabeçalho - conteúdo não importa, só a posição das linhas de dado
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def builder():
    linhas = [
        _linha("GOC24129", 1000, "5465"),
        _linha("BBI25018", 500, "5465"),  # NF 5465 compartilhada - caso real confirmado
        _linha("GOC25129", 2000, "9001"),  # NF exclusiva de um único processo
        _linha("GOC24999", "SEM INFO", "9999"),  # quantidade não numérica - deve ser ignorada
    ]
    return ControleImportacoesRateioBuilder(_montar_xlsx_bytes(linhas))


def test_nfs_do_processo(builder):
    assert builder.nfs_do_processo("GOC24129") == {"5465"}
    assert builder.nfs_do_processo("BBI25018") == {"5465"}
    assert builder.nfs_do_processo("GOC25129") == {"9001"}
    assert builder.nfs_do_processo("PROCESSO-INEXISTENTE") == set()


def test_construir_matriz_nf_compartilhada(builder):
    matriz = builder.construir(["GOC24129", "BBI25018"], "5465")

    assert matriz is not None
    assert matriz.qtd_itens_total_nf == 1500
    assert matriz.fonte == "Controle PIs"

    por_processo = {p.processo_codigo: p for p in matriz.participantes}
    assert por_processo["GOC24129"].qtd_itens == 1000
    assert por_processo["GOC24129"].percentual == Decimal(1000) / Decimal(1500)
    assert por_processo["BBI25018"].qtd_itens == 500
    assert por_processo["BBI25018"].percentual == Decimal(500) / Decimal(1500)


def test_construir_retorna_none_quando_processo_nao_tem_quantidade_na_nf(builder):
    # GOC25129 não aparece na NF 5465 - não pode inventar uma quantidade
    assert builder.construir(["GOC24129", "GOC25129"], "5465") is None


def test_quantidade_nao_numerica_e_ignorada(builder):
    assert builder.nfs_do_processo("GOC24999") == set()
    assert builder.construir(["GOC24999"], "9999") is None
