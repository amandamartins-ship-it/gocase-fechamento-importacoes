from datetime import date

from pydantic import BaseModel


class ItemComposicaoResponse(BaseModel):
    categoria: str
    valor_documentos: float
    valor_contabilizado: float
    valor_rateado: float
    percentual_rateio: float | None
    diferenca: float


class FechamentoProcessoResponse(BaseModel):
    processo_codigo: str
    mes_referencia: date
    status: str
    saldo_final: float
    variacao_cambial: float | None
    motivos_pendencia: list[str]
    composicao: list[ItemComposicaoResponse]


class ResumoProcessamentoFechamentoResponse(BaseModel):
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
    resultados: list[FechamentoProcessoResponse]
