"""Sinônimos de histórico -> categoria contábil, conforme a lista do pedido
original (Frete, Armazenagem, Honorários, AFRMM, Seguro, Capatazia, IOF,
Mercadoria, Numerário, Reembolso, NF Entrada, Variação Cambial, Outras
despesas). Aplicado sobre o histórico já normalizado (sem acento, minúsculo)."""

import re

from app.domain.entities import CategoriaLancamento

# ordem importa: mais específico primeiro (ex "nf entrada" antes de "mercadoria")
REGRAS: list[tuple[re.Pattern, CategoriaLancamento]] = [
    (re.compile(r"\bafrmm\b"), CategoriaLancamento.AFRMM),
    (re.compile(r"\bnf\s*entrada\b|nota fiscal de entrada|entrada de mercadoria"), CategoriaLancamento.NF_ENTRADA),
    (re.compile(r"variacao cambial|var\.?\s*cambial|ajuste cambial"), CategoriaLancamento.VARIACAO_CAMBIAL),
    (re.compile(r"\breembolso\b"), CategoriaLancamento.REEMBOLSO),
    (re.compile(r"\bnumerario\b|adiantamento.*numerario"), CategoriaLancamento.NUMERARIO),
    (re.compile(r"\barmazenagem\b|\barmazem\b|\barmazenamento\b"), CategoriaLancamento.ARMAZENAGEM),
    (re.compile(r"\bhonorarios?\b"), CategoriaLancamento.HONORARIOS),
    (re.compile(r"\bcapatazia\b"), CategoriaLancamento.CAPATAZIA),
    (re.compile(r"\bseguro\b"), CategoriaLancamento.SEGURO),
    (re.compile(r"\biof\b"), CategoriaLancamento.IOF),
    (re.compile(r"\bicms\b"), CategoriaLancamento.OUTRAS_DESPESAS),  # ICMS não tem categoria própria no pedido original
    (re.compile(r"\bfrete\b"), CategoriaLancamento.FRETE),
    (re.compile(r"\bmercadoria\b|compra.*importacao|importacao.*mercadoria"), CategoriaLancamento.MERCADORIA),
]


def classificar_historico(historico_normalizado: str) -> CategoriaLancamento:
    for padrao, categoria in REGRAS:
        if padrao.search(historico_normalizado):
            return categoria
    return CategoriaLancamento.OUTRAS_DESPESAS
