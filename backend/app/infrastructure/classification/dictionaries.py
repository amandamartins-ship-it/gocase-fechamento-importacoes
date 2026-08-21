"""Dicionários de classificação de documentos por nome de arquivo/caminho.

Construído a partir de uma amostra real de processos no Drive (GOC25129,
GOC25191 - serviço, BBI25167 - múltiplos embarques). Duas listas ordenadas
(mais específico primeiro, retorna no primeiro match):

- GERAL: documentos do embarque em geral (DI/DUIMP, PL, CI/PI, NF, etc.)
- FATURAMENTO_FINAL: arquivos dentro de uma pasta "<Trading> - FATURAMENTO
  FINAL (...)" - cada trading nomeia diferente (WMF usa "1 - FRETE
  INTERNACIONAL.pdf" numerado; CODELI usa siglas tipo "-ND"/"-NF"/"-REC") -
  por isso o contexto muda o dicionário aplicado, não só o nome do arquivo.
"""

import re

from app.domain.entities import TipoDocumento

# (regex sobre o nome do arquivo, case-insensitive, tipo)
GERAL: list[tuple[re.Pattern, TipoDocumento]] = [
    (re.compile(r"protocolo\s*di", re.I), TipoDocumento.PROTOCOLO_DI),
    (re.compile(r"rascunho.*nota\s*fiscal", re.I), TipoDocumento.RASCUNHO_NF_ENTRADA),
    (re.compile(r"\bcomprovante\s*de\s*importa[cç][aã]o\b", re.I), TipoDocumento.COMPROVANTE_IMPORTACAO),
    (re.compile(r"relat[oó]rio\s*de\s*itens", re.I), TipoDocumento.RELATORIO_ITENS),
    (re.compile(r"instru[cç][aã]o\s*de\s*desembara[cç]o", re.I), TipoDocumento.INSTRUCAO_DESEMBARACO),
    # Numerário/ICMS checados antes de DUIMP/NF: um comprovante de numerário costuma citar
    # a DUIMP/DI a que se refere no próprio nome do arquivo (ex "NUMERÁRIO - DUIMP - ..."),
    # mas a natureza do documento é o pagamento, não a declaração em si.
    (re.compile(r"numer[aá]rio", re.I), TipoDocumento.NUMERARIO),
    (re.compile(r"\bicms\b", re.I), TipoDocumento.ICMS),
    # DUIMP é a substituta da DI (declaração de importação) - mesma natureza contábil.
    (re.compile(r"\bduimp\b|\bdi\s*-|\bdi\s+\d|^di\b", re.I), TipoDocumento.DI),
    (re.compile(r"\bpacking\s*list\b|(?<![a-z])pl\s*-|-\s*pl\b|-\s*pl\s", re.I), TipoDocumento.PACKING_LIST),
    (re.compile(r"\bglme\b", re.I), TipoDocumento.GLME),
    # HAWB/OHAWB/AWB/HBL/HBL - conhecimentos de embarque aéreo/marítimo.
    (re.compile(r"\b(o?hawb|awb|h?bl)\b", re.I), TipoDocumento.AWB_HAWB),
    (re.compile(r"\.xml$", re.I), TipoDocumento.XML_NFE),
    (re.compile(r"\bnf\b|\bnota\s*fiscal\b", re.I), TipoDocumento.NOTA_FISCAL),
    # CI (commercial invoice) e PI (proforma invoice) - mesmo balde "Invoice" do pedido original.
    (re.compile(r"(?<![a-z])ci\s*-|-\s*ci\b|-\s*ci\s|^ci-", re.I), TipoDocumento.INVOICE_CI),
    (re.compile(r"(?<![a-z])pi\s*-|-\s*pi\b|-\s*pi\s|^pi-", re.I), TipoDocumento.INVOICE_CI),
]

FATURAMENTO_FINAL: list[tuple[re.Pattern, TipoDocumento]] = [
    (re.compile(r"frete\s*internacional|^\s*1\s*-", re.I), TipoDocumento.FRETE_INTERNACIONAL),
    (re.compile(r"\bicms\b|^\s*2\s*-", re.I), TipoDocumento.ICMS),
    (re.compile(r"armazenagem|^\s*3\s*-", re.I), TipoDocumento.ARMAZENAGEM),
    (re.compile(r"frete\s*entrega|^\s*4\s*-", re.I), TipoDocumento.FRETE_ENTREGA),
    (re.compile(r"honor[aá]rios|^\s*5\s*-", re.I), TipoDocumento.HONORARIOS),
    (re.compile(r"numer[aá]rio|^\s*6\s*-", re.I), TipoDocumento.NUMERARIO),
    (re.compile(r"presta[cç][aã]o\s*de\s*contas|^\s*7\s*-", re.I), TipoDocumento.PRESTACAO_CONTAS),
    (re.compile(r"devolu[cç][aã]o.*saldo|dev\s*saldo|^\s*8\s*-", re.I), TipoDocumento.DEVOLUCAO_SALDO),
    # Siglas específicas de trading (ex CODELI "-ND"/"-NF"/"-REC") são ambíguas o suficiente para
    # não adivinhar a categoria de despesa - ficam OUTRO e viram pendência explícita no fechamento
    # em vez de arriscar um valor no lugar errado (ver app/domain/entities.py StatusFechamento).
]


def caminho_indica_faturamento_final(caminho: str) -> bool:
    return bool(re.search(r"faturamento\s*final", caminho, re.I))


def classificar_por_nome(nome_arquivo: str, caminho: str) -> TipoDocumento:
    regras = FATURAMENTO_FINAL if caminho_indica_faturamento_final(caminho) else GERAL
    for padrao, tipo in regras:
        if padrao.search(nome_arquivo):
            return tipo
    return TipoDocumento.OUTRO
