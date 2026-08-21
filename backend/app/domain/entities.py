"""Entidades de domínio puras - sem dependência de framework/ORM.

Usadas pelos casos de uso em app/application; a camada de infraestrutura
converte de/para os modelos SQLAlchemy em app/infrastructure/db/models.py.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TipoDocumento(StrEnum):
    DI = "DI"
    INVOICE_CI = "INVOICE_CI"
    PACKING_LIST = "PACKING_LIST"
    GLME = "GLME"
    AWB_HAWB = "AWB_HAWB"
    NOTA_FISCAL = "NOTA_FISCAL"
    XML_NFE = "XML_NFE"
    NUMERARIO = "NUMERARIO"
    ICMS = "ICMS"
    PROTOCOLO_DI = "PROTOCOLO_DI"
    RASCUNHO_NF_ENTRADA = "RASCUNHO_NF_ENTRADA"
    COMPROVANTE_IMPORTACAO = "COMPROVANTE_IMPORTACAO"
    RELATORIO_ITENS = "RELATORIO_ITENS"
    INSTRUCAO_DESEMBARACO = "INSTRUCAO_DESEMBARACO"
    FRETE_INTERNACIONAL = "FRETE_INTERNACIONAL"
    FRETE_ENTREGA = "FRETE_ENTREGA"
    ARMAZENAGEM = "ARMAZENAGEM"
    HONORARIOS = "HONORARIOS"
    PRESTACAO_CONTAS = "PRESTACAO_CONTAS"
    DEVOLUCAO_SALDO = "DEVOLUCAO_SALDO"
    OUTRO = "OUTRO"


class CategoriaLancamento(StrEnum):
    FRETE = "Frete"
    ARMAZENAGEM = "Armazenagem"
    HONORARIOS = "Honorários"
    AFRMM = "AFRMM"
    SEGURO = "Seguro"
    CAPATAZIA = "Capatazia"
    IOF = "IOF"
    MERCADORIA = "Mercadoria"
    NUMERARIO = "Numerário"
    REEMBOLSO = "Reembolso"
    NF_ENTRADA = "NF Entrada"
    VARIACAO_CAMBIAL = "Variação Cambial"
    OUTRAS_DESPESAS = "Outras despesas"


class StatusFechamento(StrEnum):
    FECHADO = "Fechado"
    PENDENTE = "Pendente"
    BLOQUEADO = "Bloqueado"


class StatusLeituraDocumento(StrEnum):
    OK = "OK"
    SEM_TEXTO = "SEM_TEXTO"
    OCR_APLICADO = "OCR_APLICADO"
    ERRO = "ERRO"
    PENDENTE = "PENDENTE"


@dataclass
class DocumentoRef:
    drive_file_id: str
    nome_arquivo: str
    caminho: str
    mime_type: str | None = None


@dataclass
class Documento:
    ref: DocumentoRef
    tipo: TipoDocumento
    texto_extraido: str | None = None
    valor_extraido: Decimal | None = None
    status_leitura: StatusLeituraDocumento = StatusLeituraDocumento.PENDENTE
    id: int | None = None


@dataclass
class Embarque:
    codigo: str  # ex GOC25129.1
    drive_folder_id: str
    trading: str | None = None
    referencia_trading: str | None = None
    documentos: list[Documento] = field(default_factory=list)
    id: int | None = None


@dataclass
class Processo:
    codigo: str  # ex GOC25129
    empresa_codigo: str  # GOC, BBI
    descricao: str | None = None
    fornecedor: str | None = None
    ano: int | None = None
    drive_folder_id: str | None = None
    embarques: list[Embarque] = field(default_factory=list)
    id: int | None = None


@dataclass
class LancamentoRazao:
    mes_referencia: date
    historico: str
    valor_debito: Decimal
    valor_credito: Decimal
    empresa: str | None = None
    conta_contabil: str | None = None  # conta numérica (ex "Conta" 113103)
    numero_contabil: str | None = None  # referência do lançamento (ex "NR: 000011059592")
    unidade: str | None = None  # centro de custo
    data: date | None = None  # data do lançamento em si (mes_referencia é só o mês agrupador)
    documento_ref: str | None = None
    processos_codigos: list[str] = field(default_factory=list)
    categoria_classificada: CategoriaLancamento | None = None
    rateio_aplicado: bool = False
    id: int | None = None


@dataclass
class RateioParticipante:
    processo_codigo: str
    qtd_itens: int
    percentual: Decimal
    valor_destinado: Decimal


@dataclass
class MatrizRateio:
    """Memória de cálculo do rateio de uma NF compartilhada entre processos."""

    nf_referencia: str
    qtd_itens_total_nf: int
    participantes: list[RateioParticipante]
    fonte: str | None = None


@dataclass
class ItemComposicao:
    categoria: CategoriaLancamento
    valor_documentos: Decimal
    valor_contabilizado: Decimal
    valor_rateado: Decimal
    percentual_rateio: Decimal | None
    diferenca: Decimal


@dataclass
class ComposicaoContabil:
    processo_codigo: str
    mes_referencia: date
    itens: list[ItemComposicao]


@dataclass
class LinhaRazaoRateada:
    """Uma linha do Razão já "explodida" por processo participante - o mesmo
    resultado que a equipe monta manualmente copiando a linha original N vezes
    (uma por processo) e dividindo o valor pelo rateio. Espelha as colunas
    reais de 'Importações em Andamento'/'Processos Fechados'."""

    empresa: str | None
    data: date | None
    conta: str | None
    numero_contabil: str | None
    unidade: str | None
    historico: str
    debito: Decimal
    credito: Decimal
    processo: str  # código específico citado no histórico (com sufixo de embarque, quando houver)
    processo_full: str  # código base do processo
    status: str | None = None  # status de fechamento calculado (Fechado/Pendente/Bloqueado)
    lancamento_id: int | None = None

    @property
    def movimentacao(self) -> Decimal:
        return self.debito - self.credito

    @property
    def processo_controle_importacao(self) -> str:
        return self.processo.replace(".", "-")


@dataclass
class ResultadoFechamento:
    processo_codigo: str
    mes_referencia: date
    status: StatusFechamento
    saldo_final: Decimal
    variacao_cambial: Decimal | None
    motivos_pendencia: list[str]
