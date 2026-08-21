"""Extrai o valor pago de um documento da pasta "FATURAMENTO FINAL" (Frete,
Armazenagem, Honorários, Numerário etc.) - PDF real, sem OCR (esses
documentos têm camada de texto real, confirmado abrindo 3 exemplos reais em
2026-07-26: DAI da Infraero para Armazenagem, NFS-e municipal para
Honorários, fatura própria da trading para Frete Internacional).

Cada um desses formatos institucionais tem seu próprio jeito de dizer "isto é
o valor devido", mas todos terminam com um comprovante de pagamento bancário
que reafirma o mesmo valor de forma simples - por isso a estratégia é: varrer
o texto inteiro por QUALQUER marcador conhecido e usar a ÚLTIMA ocorrência
(o comprovante de pagamento vem depois do documento original, então "o
valor realmente pago" naturalmente vence sobre valores parciais/tabelas
citados antes). Nunca inventa um valor - se nenhum marcador bate, retorna
None e o documento fica pendente de revisão manual.
"""

import io
import re
from decimal import Decimal

import pdfplumber

from app.infrastructure.razao.valores import parse_valor_brl

# ordem não importa para a escolha final (vence quem aparece por último no
# texto) - mas cada regex precisa ser específica o suficiente pra não pegar
# um número errado (ex: peso, taxa de câmbio, código de barras).
MARCADORES_VALOR: list[re.Pattern] = [
    re.compile(r"valor\s+total\s+da\s+nfs-?e\D{0,20}?([\d.]{1,12},\d{2})", re.I),
    re.compile(r"valor\s+l[ií]quido\s+da\s+nfs-?e\D{0,20}?([\d.]{1,12},\d{2})", re.I),
    re.compile(r"total\s*:\s*([\d.]{1,12},\d{2})", re.I),
    re.compile(r"valor\s+total\D{0,10}?([\d.]{1,12},\d{2})", re.I),
    re.compile(r"valor\s+a\s+pagar\s+([\d.]{1,12},\d{2})", re.I),
    re.compile(r"valor\s+pago\D{0,10}?([\d.]{1,12},\d{2})", re.I),
    re.compile(r"valor\s+r\$\s*([\d.]{1,12},\d{2})", re.I),
]

PDF_MIME_TYPES = {"application/pdf"}


def extrair_texto_pdf(conteudo: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            return "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception:  # noqa: BLE001 - PDF corrompido/protegido: sem texto, não é erro fatal
        return ""


def extrair_valor_do_texto(texto: str) -> Decimal | None:
    melhor_posicao = -1
    melhor_valor: Decimal | None = None
    for padrao in MARCADORES_VALOR:
        for match in padrao.finditer(texto):
            if match.start() <= melhor_posicao:
                continue
            valor = parse_valor_brl(match.group(1))
            if valor > 0:
                melhor_posicao = match.start()
                melhor_valor = valor
    return melhor_valor


def extrair_valor_documento(conteudo: bytes, mime_type: str | None) -> Decimal | None:
    if mime_type not in PDF_MIME_TYPES:
        return None  # xlsx/imagem: fora do escopo desta primeira fatia (ver Fase 9)
    texto = extrair_texto_pdf(conteudo)
    if not texto:
        return None  # PDF só-imagem (sem camada de texto) - ficaria para uma etapa de OCR futura
    return extrair_valor_do_texto(texto)
