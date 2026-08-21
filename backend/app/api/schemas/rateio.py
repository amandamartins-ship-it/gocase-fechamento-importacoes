from pydantic import BaseModel


class ResumoAplicacaoRateioResponse(BaseModel):
    total_lancamentos_multi_processo: int
    aplicados: int
    pendentes: int
    motivos_pendencia: list[dict]


class AuditoriaRateioResponse(BaseModel):
    memoria: dict
