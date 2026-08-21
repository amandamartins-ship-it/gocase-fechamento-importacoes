from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import entities
from app.domain.processo_codigo import processo_base
from app.infrastructure.db import models


class SqlAlchemyRazaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def salvar_lote(self, lancamentos: list[entities.LancamentoRazao]) -> None:
        if not lancamentos:
            return
        mes_referencia = lancamentos[0].mes_referencia

        # reenvio do mesmo mês substitui o lote anterior por inteiro - o Razão é
        # sempre a "foto" final daquele mês, não um acúmulo de uploads.
        existentes = self.db.scalars(
            select(models.RazaoLancamento).where(models.RazaoLancamento.mes_referencia == mes_referencia)
        ).all()
        for row in existentes:
            self.db.delete(row)
        self.db.flush()

        for lancamento in lancamentos:
            self.db.add(
                models.RazaoLancamento(
                    mes_referencia=lancamento.mes_referencia,
                    data=lancamento.data,
                    empresa=lancamento.empresa,
                    conta_contabil=lancamento.conta_contabil,
                    numero_contabil=lancamento.numero_contabil,
                    unidade=lancamento.unidade,
                    historico=lancamento.historico,
                    processos_codigos=lancamento.processos_codigos,
                    documento_ref=lancamento.documento_ref,
                    valor_debito=lancamento.valor_debito,
                    valor_credito=lancamento.valor_credito,
                    categoria_classificada=(
                        str(lancamento.categoria_classificada) if lancamento.categoria_classificada else None
                    ),
                    rateio_aplicado=lancamento.rateio_aplicado,
                )
            )
        self.db.commit()

    def listar_por_processo(self, processo_codigo: str, mes_referencia: date) -> list[entities.LancamentoRazao]:
        rows = self.db.scalars(
            select(models.RazaoLancamento).where(models.RazaoLancamento.mes_referencia == mes_referencia)
        ).all()
        # compara pela base do processo (sem sufixo de embarque) - um lançamento
        # que cita "GOC25129.1" também pertence ao processo "GOC25129".
        return [
            self._to_domain(row)
            for row in rows
            if processo_codigo in {processo_base(c) for c in (row.processos_codigos or [])}
        ]

    def listar_multi_processo_pendentes(self, mes_referencia: date) -> list[entities.LancamentoRazao]:
        rows = self.db.scalars(
            select(models.RazaoLancamento).where(
                models.RazaoLancamento.mes_referencia == mes_referencia,
                models.RazaoLancamento.rateio_aplicado.is_(False),
            )
        ).all()
        pendentes = []
        for row in rows:
            bases = {processo_base(c) for c in (row.processos_codigos or [])}
            if len(bases) >= 2:
                pendentes.append(self._to_domain(row))
        return pendentes

    def listar_processos_citados(self, mes_referencia: date) -> list[str]:
        """Códigos-base (sem sufixo de embarque) de todo processo citado em algum
        lançamento do mês - usado para saber quais processos têm fechamento a processar."""
        rows = self.db.scalars(
            select(models.RazaoLancamento).where(models.RazaoLancamento.mes_referencia == mes_referencia)
        ).all()
        bases: set[str] = set()
        for row in rows:
            bases.update(processo_base(c) for c in (row.processos_codigos or []))
        return sorted(bases)

    def marcar_rateio_aplicado(self, lancamento_id: int) -> None:
        row = self.db.get(models.RazaoLancamento, lancamento_id)
        if row is not None:
            row.rateio_aplicado = True
            self.db.commit()

    def listar_todos(self, mes_referencia: date) -> list[entities.LancamentoRazao]:
        rows = self.db.scalars(
            select(models.RazaoLancamento)
            .where(models.RazaoLancamento.mes_referencia == mes_referencia)
            .order_by(models.RazaoLancamento.data, models.RazaoLancamento.id)
        ).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: models.RazaoLancamento) -> entities.LancamentoRazao:
        return entities.LancamentoRazao(
            id=row.id,
            mes_referencia=row.mes_referencia,
            data=row.data,
            historico=row.historico,
            valor_debito=row.valor_debito,
            valor_credito=row.valor_credito,
            empresa=row.empresa,
            conta_contabil=row.conta_contabil,
            numero_contabil=row.numero_contabil,
            unidade=row.unidade,
            documento_ref=row.documento_ref,
            processos_codigos=row.processos_codigos or [],
            categoria_classificada=(
                entities.CategoriaLancamento(row.categoria_classificada) if row.categoria_classificada else None
            ),
            rateio_aplicado=row.rateio_aplicado,
        )
