"""Lê a aba "Controle PIs" de Controle de Importações.xlsx (a planilha mestre
de Comex) para montar a Matriz Mestre de Rateio.

Layout confirmado em 2026-07-24 abrindo o arquivo real (colunas por nome,
índice abaixo por robustez a pequenas variações futuras de coluna): 'Processo'
(A), 'Quantidade' (G) e 'NF' (AV) - a coluna NF É de fato compartilhada entre
processos diferentes quando várias compras são consolidadas na mesma nota
fiscal (confirmado: 61 NFs compartilhadas por 2+ processos na amostra real).
Isso é exatamente a "Quantidade de Itens da NF" que o rateio precisa.

Sempre baixe o arquivo pela Drive API (bytes em memória) - não existe o
problema de truncamento do path montado do Drive (G:\\...) porque não estamos
lendo do filesystem montado, e sim de bytes já baixados.
"""

import io
from collections import defaultdict
from decimal import Decimal

import openpyxl

from app.domain.entities import MatrizRateio, RateioParticipante

ABA = "Controle PIs"
COL_PROCESSO = 0
COL_QUANTIDADE = 6
COL_NF = 47


class ControleImportacoesRateioBuilder:
    def __init__(self, conteudo_xlsx: bytes):
        self._quantidade_por_processo_nf: dict[tuple[str, str], int] = {}
        self._nfs_por_processo: dict[str, set[str]] = defaultdict(set)
        self._carregar(conteudo_xlsx)

    def _carregar(self, conteudo: bytes) -> None:
        workbook = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
        try:
            planilha = workbook[ABA]
            for linha in planilha.iter_rows(min_row=2, values_only=True):
                if len(linha) <= COL_NF:
                    continue
                processo, quantidade, nf = linha[COL_PROCESSO], linha[COL_QUANTIDADE], linha[COL_NF]
                if not processo or nf in (None, ""):
                    continue
                if not isinstance(quantidade, (int, float)):
                    continue  # ex "SEM INFO"/erro de fórmula - não soma valor não-numérico
                processo = str(processo).strip()
                nf = str(nf).strip()
                chave = (processo, nf)
                self._quantidade_por_processo_nf[chave] = (
                    self._quantidade_por_processo_nf.get(chave, 0) + quantidade
                )
                self._nfs_por_processo[processo].add(nf)
        finally:
            workbook.close()

    def nfs_do_processo(self, processo_codigo: str) -> set[str]:
        return set(self._nfs_por_processo.get(processo_codigo, set()))

    def construir(self, processos_codigos: list[str], nf_referencia: str) -> MatrizRateio | None:
        quantidades: dict[str, int] = {}
        for processo in processos_codigos:
            quantidade = self._quantidade_por_processo_nf.get((processo, nf_referencia))
            if not quantidade or quantidade <= 0:
                return None  # sem quantidade real para algum processo citado - não força um rateio
            quantidades[processo] = int(quantidade)

        total = sum(quantidades.values())
        participantes = [
            RateioParticipante(
                processo_codigo=processo,
                qtd_itens=quantidade,
                percentual=Decimal(quantidade) / Decimal(total),
                valor_destinado=Decimal("0"),
            )
            for processo, quantidade in quantidades.items()
        ]
        return MatrizRateio(
            nf_referencia=nf_referencia,
            qtd_itens_total_nf=total,
            participantes=participantes,
            fonte=ABA,
        )
