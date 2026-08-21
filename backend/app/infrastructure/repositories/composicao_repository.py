from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import entities
from app.infrastructure.db import models
from app.infrastructure.repositories.processo_repository import get_or_create_processo_minimo


class SqlAlchemyComposicaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def salvar(self, composicao: entities.ComposicaoContabil) -> None:
        processo = get_or_create_processo_minimo(self.db, composicao.processo_codigo)

        antigos = self.db.scalars(
            select(models.ComposicaoContabil).where(
                models.ComposicaoContabil.processo_id == processo.id,
                models.ComposicaoContabil.mes_referencia == composicao.mes_referencia,
            )
        ).all()
        for row in antigos:
            self.db.delete(row)
        self.db.flush()

        for item in composicao.itens:
            self.db.add(
                models.ComposicaoContabil(
                    processo_id=processo.id,
                    mes_referencia=composicao.mes_referencia,
                    categoria=str(item.categoria),
                    valor_documentos=item.valor_documentos,
                    valor_contabilizado=item.valor_contabilizado,
                    valor_rateado=item.valor_rateado,
                    percentual_rateio=item.percentual_rateio,
                    diferenca=item.diferenca,
                )
            )
        self.db.commit()

    def listar(self, processo_codigo: str, mes_referencia) -> list[entities.ItemComposicao]:
        processo = self.db.scalar(select(models.Processo).where(models.Processo.codigo == processo_codigo))
        if processo is None:
            return []
        rows = self.db.scalars(
            select(models.ComposicaoContabil).where(
                models.ComposicaoContabil.processo_id == processo.id,
                models.ComposicaoContabil.mes_referencia == mes_referencia,
            )
        ).all()
        return [
            entities.ItemComposicao(
                categoria=entities.CategoriaLancamento(row.categoria),
                valor_documentos=row.valor_documentos,
                valor_contabilizado=row.valor_contabilizado,
                valor_rateado=row.valor_rateado,
                percentual_rateio=row.percentual_rateio,
                diferenca=row.diferenca,
            )
            for row in rows
        ]
