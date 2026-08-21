"""Conversão de valores monetários no formato brasileiro (ponto de milhar,
vírgula decimal) - mesma convenção usada no pipeline de conciliação bancária
(ver memória gocase_reconciliation_pipeline). Também tolera notação
científica (ex "1.024771826E7"), gotcha real já visto num export de CSV."""

import re
from decimal import Decimal, InvalidOperation

_CIENTIFICA = re.compile(r"^-?\d+(\.\d+)?[eE][+-]?\d+$")


def parse_valor_brl(texto: str | None) -> Decimal:
    if texto is None:
        return Decimal("0")
    texto = texto.strip()
    if not texto:
        return Decimal("0")

    if _CIENTIFICA.match(texto):
        try:
            return Decimal(texto)
        except InvalidOperation:
            return Decimal("0")

    negativo = texto.startswith("(") and texto.endswith(")")
    if negativo:
        texto = texto[1:-1]
    texto = texto.replace("R$", "").strip()

    if "," in texto:
        # formato BR: ponto = milhar, vírgula = decimal
        texto = texto.replace(".", "").replace(",", ".")

    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return Decimal("0")
    return -valor if negativo else valor
