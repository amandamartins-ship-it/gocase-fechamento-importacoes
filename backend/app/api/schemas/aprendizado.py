from datetime import datetime

from pydantic import BaseModel, field_validator

from app.domain.entities import CategoriaLancamento, TipoDocumento

TIPOS_VALIDOS = {"classificacao", "documento"}


class CorrecaoRequest(BaseModel):
    tipo: str  # "classificacao" (categoria de lançamento) ou "documento" (tipo de documento)
    padrao: str  # trecho do histórico / nome de arquivo que identifica os casos a corrigir
    valor_corrigido: str
    justificativa: str | None = None

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in TIPOS_VALIDOS:
            raise ValueError(f"tipo deve ser um de {sorted(TIPOS_VALIDOS)}")
        return v

    @field_validator("padrao")
    @classmethod
    def padrao_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("padrao não pode ser vazio")
        return v.strip()

    @field_validator("valor_corrigido")
    @classmethod
    def valor_corrigido_valido(cls, v: str, info) -> str:
        tipo = info.data.get("tipo")
        if tipo == "classificacao":
            valores_validos = {str(c) for c in CategoriaLancamento}
        elif tipo == "documento":
            valores_validos = {str(t) for t in TipoDocumento}
        else:
            return v
        if v not in valores_validos:
            raise ValueError(f"valor_corrigido inválido para tipo={tipo}. Valores aceitos: {sorted(valores_validos)}")
        return v


class RegraAprendidaResponse(BaseModel):
    id: int
    tipo: str
    padrao: str
    valor_corrigido: str
    justificativa: str | None
    criado_por: str | None
    criado_em: datetime
