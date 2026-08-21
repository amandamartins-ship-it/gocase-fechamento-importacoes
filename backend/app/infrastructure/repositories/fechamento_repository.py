from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import entities
from app.infrastructure.db import models
from app.infrastructure.repositories.processo_repository import get_or_create_processo_minimo


class SqlAlchemyFechamentoRepository:
    def __init__(self, db: Session):
        self.db = db

    def salvar(self, resultado: entities.ResultadoFechamento) -> None:
        processo = get_or_create_processo_minimo(self.db, resultado.processo_codigo)

        row = self.db.scalar(
            select(models.Fechamento).where(
                models.Fechamento.processo_id == processo.id,
                models.Fechamento.mes_referencia == resultado.mes_referencia,
            )
        )
        if row is None:
            row = models.Fechamento(processo_id=processo.id, mes_referencia=resultado.mes_referencia)
            self.db.add(row)

        row.status = str(resultado.status)
        row.saldo_final = resultado.saldo_final
        row.variacao_cambial = resultado.variacao_cambial
        row.motivos_pendencia = resultado.motivos_pendencia
        self.db.commit()

    def buscar(self, processo_codigo: str, mes_referencia: date) -> entities.ResultadoFechamento | None:
        processo = self.db.scalar(select(models.Processo).where(models.Processo.codigo == processo_codigo))
        if processo is None:
            return None
        row = self.db.scalar(
            select(models.Fechamento).where(
                models.Fechamento.processo_id == processo.id,
                models.Fechamento.mes_referencia == mes_referencia,
            )
        )
        return self._to_domain(row, processo_codigo) if row else None

    def listar_por_mes(self, mes_referencia: date) -> list[entities.ResultadoFechamento]:
        rows = self.db.scalars(
            select(models.Fechamento).where(models.Fechamento.mes_referencia == mes_referencia)
        ).all()
        return [self._to_domain(row, row.processo.codigo) for row in rows]

    @staticmethod
    def _to_domain(row: models.Fechamento, processo_codigo: str) -> entities.ResultadoFechamento:
        return entities.ResultadoFechamento(
            processo_codigo=processo_codigo,
            mes_referencia=row.mes_referencia,
            status=entities.StatusFechamento(row.status),
            saldo_final=row.saldo_final,
            variacao_cambial=row.variacao_cambial,
            motivos_pendencia=row.motivos_pendencia or [],
        )
