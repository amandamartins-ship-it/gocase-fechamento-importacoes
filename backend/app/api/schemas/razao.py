from datetime import date

from pydantic import BaseModel


class ResumoImportacaoRazaoResponse(BaseModel):
    mes_referencia: date | None
    total_lancamentos: int
    total_valor_debito: float
    total_valor_credito: float
    processos_citados: list[str]
    lancamentos_sem_processo: int
    lancamentos_multi_processo: int
    por_categoria: dict[str, int]
