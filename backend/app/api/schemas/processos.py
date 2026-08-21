from datetime import date

from pydantic import BaseModel


class LancamentoResumoResponse(BaseModel):
    id: int | None
    historico: str
    categoria: str | None
    valor_debito: float
    valor_credito: float
    processos_codigos: list[str]
    rateio_aplicado: bool


class LinhaRateadaResponse(BaseModel):
    lancamento_id: int | None
    empresa: str | None
    data: date | None
    conta: str | None
    numero_contabil: str | None
    unidade: str | None
    historico: str
    debito: float
    credito: float
    movimentacao: float
    processo: str
    processo_full: str
    processo_controle_importacao: str
    status: str | None


class LinhasRateadasProcessoResponse(BaseModel):
    linhas: list[LinhaRateadaResponse]
    total_debito: float
    total_credito: float
    saldo_processo: float


class ProcessoResumoResponse(BaseModel):
    codigo: str
    empresa_codigo: str
    descricao: str | None
    fornecedor: str | None
    status: str | None
    saldo_final: float | None


class ExtracaoValoresResponse(BaseModel):
    documentos_processados: int
    documentos_com_valor_encontrado: int


class DashboardIndicadoresResponse(BaseModel):
    total_processos: int
    processos_fechados: int
    processos_pendentes: int
    processos_bloqueados: int
    valor_total_contabilizado: float
    valor_total_rateado: float
    valor_pendente: float
    total_variacao_cambial: float
    percentual_automacao: float
    indice_qualidade_fechamento: float
