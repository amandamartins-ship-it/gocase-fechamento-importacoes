from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.aprendizado import CorrecaoRequest, RegraAprendidaResponse
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.regras_aprendidas_repository import SqlAlchemyRegrasAprendidasRepository

router = APIRouter(prefix="/aprendizado", tags=["aprendizado"])


@router.post("/corrigir", status_code=201)
def corrigir(
    correcao: CorrecaoRequest,
    email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    repo = SqlAlchemyRegrasAprendidasRepository(db)
    repo.registrar(correcao.tipo, correcao.padrao, correcao.valor_corrigido, correcao.justificativa, email)
    return {
        "mensagem": (
            "Correção salva - vale a partir do próximo upload do Razão ou sincronização do Drive "
            "(não reprocessa automaticamente o que já foi importado)."
        )
    }


@router.get("/regras", response_model=list[RegraAprendidaResponse])
def listar_regras(
    tipo: str | None = None,
    _email: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return SqlAlchemyRegrasAprendidasRepository(db).listar(tipo)
