from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db import models


class SqlAlchemyRateioRepository:
    def __init__(self, db: Session):
        self.db = db

    def salvar_participante(
        self,
        processo_codigo: str,
        nf_referencia: str,
        qtd_itens_processo: int,
        qtd_itens_total_nf: int,
        percentual: object,
        fonte: str | None,
    ) -> None:
        processo_row = self.db.scalar(select(models.Processo).where(models.Processo.codigo == processo_codigo))
        if processo_row is None:
            # processo ainda não sincronizado via Drive (Fase 2) - a matriz-cache fica pendente,
            # mas isso não bloqueia a auditoria do rateio em si (ver AuditoriaCalculo).
            return

        existente = self.db.scalar(
            select(models.RateioMatriz).where(
                models.RateioMatriz.processo_id == processo_row.id,
                models.RateioMatriz.nf_referencia == nf_referencia,
            )
        )
        if existente is None:
            existente = models.RateioMatriz(processo_id=processo_row.id, nf_referencia=nf_referencia)
            self.db.add(existente)
        existente.qtd_itens_processo = qtd_itens_processo
        existente.qtd_itens_total_nf = qtd_itens_total_nf
        existente.percentual = percentual
        existente.fonte = fonte
        self.db.commit()


class SqlAlchemyAuditoriaRepository:
    def __init__(self, db: Session):
        self.db = db

    def registrar(self, referencia_tipo: str, referencia_id: int, memoria: dict) -> None:
        self.db.add(
            models.AuditoriaCalculo(referencia_tipo=referencia_tipo, referencia_id=referencia_id, memoria=memoria)
        )
        self.db.commit()

    def buscar(self, referencia_tipo: str, referencia_id: int) -> dict | None:
        row = self.db.scalar(
            select(models.AuditoriaCalculo)
            .where(
                models.AuditoriaCalculo.referencia_tipo == referencia_tipo,
                models.AuditoriaCalculo.referencia_id == referencia_id,
            )
            .order_by(models.AuditoriaCalculo.criado_em.desc())
        )
        return row.memoria if row else None
