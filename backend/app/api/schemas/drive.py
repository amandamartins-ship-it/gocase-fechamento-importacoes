from pydantic import BaseModel


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


class DriveStatusResponse(BaseModel):
    conectado: bool


class ResumoSincronizacaoResponse(BaseModel):
    total_processos: int
    total_embarques: int
    total_documentos: int
    documentos_por_tipo: dict[str, int]
    processos: list[str]
