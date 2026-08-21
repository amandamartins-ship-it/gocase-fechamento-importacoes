"""Parser do Razão Contábil de Importações.

Não assume uma ordem fixa de colunas (o layout real de exportação pode variar
um pouco entre acessos ao sistema contábil) - resolve cada campo por nome de
cabeçalho, testando algumas variações conhecidas do mesmo sistema usado na
conciliação bancária (ver memória gocase_reconciliation_pipeline: `;`
delimitado, encoding latin1, vírgula decimal).
"""

import csv
import io
import re
from collections import Counter
from datetime import date, datetime

from app.domain.entities import LancamentoRazao
from app.infrastructure.razao.valores import parse_valor_brl
from app.infrastructure.util.texto import normalizar_texto

PROCESSO_REGEX = re.compile(r"(?:BBI|GOC)\d{5}(?:\.\d+)?")

# cada campo lógico tem uma lista de nomes de cabeçalho aceitos, em ordem de preferência.
# "Conta" (numérico) e "Numero Contabil" (referência "NR: ...") são colunas
# distintas no Razão real - nunca tratar como sinônimos um do outro.
CANDIDATOS_CABECALHO = {
    "conta_contabil": ["conta"],
    "numero_contabil": ["numero contabil"],
    "historico": ["historico"],
    "valor_debito": ["valor a debito", "debito"],
    "valor_credito": ["valor a credito", "credito"],
    "empresa": ["empresa"],
    "unidade": ["unidade"],
    "documento_ref": ["documento"],
    "data": ["data"],
}


def _resolver_colunas(cabecalho: list[str]) -> dict[str, int]:
    normalizados = [normalizar_texto(c) for c in cabecalho]
    colunas: dict[str, int] = {}
    for campo, candidatos in CANDIDATOS_CABECALHO.items():
        for candidato in candidatos:
            if candidato in normalizados:
                colunas[campo] = normalizados.index(candidato)
                break
    return colunas


def _decodificar(conteudo: bytes) -> str:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return conteudo.decode(encoding)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin1", errors="replace")


def _parse_data(texto: str) -> date | None:
    texto = texto.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _extrair_processos(historico: str) -> list[str]:
    encontrados = PROCESSO_REGEX.findall(historico.upper())
    vistos: list[str] = []
    for codigo in encontrados:
        if codigo not in vistos:
            vistos.append(codigo)
    return vistos


class RazaoCsvParser:
    def parse(self, conteudo: bytes, nome_arquivo: str) -> list[LancamentoRazao]:
        texto = _decodificar(conteudo)
        amostra = texto[:4096]
        try:
            delimitador = csv.Sniffer().sniff(amostra, delimiters=";,").delimiter
        except csv.Error:
            delimitador = ";"

        leitor = csv.reader(io.StringIO(texto), delimiter=delimitador)
        linhas = list(leitor)
        if not linhas:
            return []

        colunas = _resolver_colunas(linhas[0])
        faltando = [c for c in ("historico", "valor_debito", "valor_credito") if c not in colunas]
        if faltando:
            raise ValueError(
                f"Colunas obrigatórias não encontradas no cabeçalho do Razão: {', '.join(faltando)}. "
                f"Cabeçalho lido: {linhas[0]}"
            )

        datas_validas: list[date] = []
        lancamentos: list[LancamentoRazao] = []
        for linha in linhas[1:]:
            if not any(campo.strip() for campo in linha):
                continue  # linha em branco no fim do arquivo

            def campo(nome: str) -> str:
                idx = colunas.get(nome)
                return linha[idx].strip() if idx is not None and idx < len(linha) else ""

            historico = campo("historico")
            data_lancamento = _parse_data(campo("data"))
            if data_lancamento:
                datas_validas.append(data_lancamento)

            lancamentos.append(
                LancamentoRazao(
                    mes_referencia=data_lancamento or date.today().replace(day=1),
                    data=data_lancamento,
                    historico=historico,
                    valor_debito=parse_valor_brl(campo("valor_debito")),
                    valor_credito=parse_valor_brl(campo("valor_credito")),
                    empresa=campo("empresa") or None,
                    conta_contabil=campo("conta_contabil") or None,
                    numero_contabil=campo("numero_contabil") or None,
                    unidade=campo("unidade") or None,
                    documento_ref=campo("documento_ref") or None,
                    processos_codigos=_extrair_processos(historico),
                )
            )

        # o Razão é enviado um mês por vez - normaliza todos os lançamentos para o
        # mês mais frequente entre as datas lidas (tolera datas isoladas de outro
        # mês/lançamentos de ajuste sem quebrar o agrupamento mensal).
        if datas_validas:
            contagem = Counter((d.year, d.month) for d in datas_validas)
            ano_mes_mais_comum = contagem.most_common(1)[0][0]
            mes_referencia = date(ano_mes_mais_comum[0], ano_mes_mais_comum[1], 1)
            for lancamento in lancamentos:
                lancamento.mes_referencia = mes_referencia

        return lancamentos
