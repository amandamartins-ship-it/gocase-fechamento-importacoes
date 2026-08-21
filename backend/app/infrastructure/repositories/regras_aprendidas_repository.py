from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db import models
from app.infrastructure.util.texto import normalizar_texto


class SqlAlchemyRegrasAprendidasRepository:
    def __init__(self, db: Session):
        self.db = db

    def registrar(
        self, tipo: str, padrao: str, valor_corrigido: str, justificativa: str | None, criado_por: str | None
    ) -> None:
        self.db.add(
            models.RegraAprendida(
                tipo=tipo,
                padrao=padrao,
                valor_corrigido=valor_corrigido,
                justificativa=justificativa,
                criado_por=criado_por,
            )
        )
        self.db.commit()

    def buscar_valor_corrigido(self, tipo: str, texto: str) -> str | None:
        texto_normalizado = normalizar_texto(texto)
        # desempate por id quando 2 regras são criadas no mesmo segundo (criado_em
        # tem resolução de segundo) - sem isso, a ordem entre elas fica indefinida.
        regras = self.db.scalars(
            select(models.RegraAprendida)
            .where(models.RegraAprendida.tipo == tipo)
            .order_by(models.RegraAprendida.criado_em.desc(), models.RegraAprendida.id.desc())
        ).all()
        for regra in regras:
            if normalizar_texto(regra.padrao) in texto_normalizado:
                return regra.valor_corrigido
        return None

    def listar(self, tipo: str | None = None) -> list[dict]:
        query = select(models.RegraAprendida).order_by(
            models.RegraAprendida.criado_em.desc(), models.RegraAprendida.id.desc()
        )
        if tipo:
            query = query.where(models.RegraAprendida.tipo == tipo)
        regras = self.db.scalars(query).all()
        return [
            {
                "id": r.id,
                "tipo": r.tipo,
                "padrao": r.padrao,
                "valor_corrigido": r.valor_corrigido,
                "justificativa": r.justificativa,
                "criado_por": r.criado_por,
                "criado_em": r.criado_em.isoformat(),
            }
            for r in regras
        ]
