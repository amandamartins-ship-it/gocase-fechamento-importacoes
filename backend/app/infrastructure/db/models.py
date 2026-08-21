from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class Empresa(Base):
    """Empresa do grupo GOCASE que importa (GO COMERCIO / BB INDUSTRIA)."""

    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)  # GOC, BBI
    nome: Mapped[str] = mapped_column(String(120))

    processos: Mapped[list["Processo"]] = relationship(back_populates="empresa")


class Processo(Base):
    """O embarque/processo de importação - entidade principal do sistema."""

    __tablename__ = "processos"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_processo_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(20), index=True)  # ex GOC25129
    descricao: Mapped[str | None] = mapped_column(String(500))
    fornecedor: Mapped[str | None] = mapped_column(String(255))
    ano: Mapped[int | None] = mapped_column()
    drive_folder_id: Mapped[str | None] = mapped_column(String(120))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship(back_populates="processos")
    embarques: Mapped[list["Embarque"]] = relationship(
        back_populates="processo", cascade="all, delete-orphan"
    )
    rateios: Mapped[list["RateioMatriz"]] = relationship(back_populates="processo")
    composicoes: Mapped[list["ComposicaoContabil"]] = relationship(back_populates="processo")
    fechamentos: Mapped[list["Fechamento"]] = relationship(back_populates="processo")


class Embarque(Base):
    """Sub-processo/embarque específico (ex GOC25129.1), vinculado a uma trading."""

    __tablename__ = "embarques"
    __table_args__ = (UniqueConstraint("processo_id", "codigo", name="uq_embarque_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column(String(30), index=True)  # ex GOC25129.1
    trading: Mapped[str | None] = mapped_column(String(120))
    referencia_trading: Mapped[str | None] = mapped_column(String(120))  # ex WMFIA261430
    drive_folder_id: Mapped[str | None] = mapped_column(String(120))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    processo: Mapped["Processo"] = relationship(back_populates="embarques")
    documentos: Mapped[list["Documento"]] = relationship(
        back_populates="embarque", cascade="all, delete-orphan"
    )


class Documento(Base):
    """Documento localizado no Drive para um embarque, já classificado por tipo."""

    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    embarque_id: Mapped[int] = mapped_column(ForeignKey("embarques.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    drive_file_id: Mapped[str] = mapped_column(String(120))
    nome_arquivo: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    texto_extraido: Mapped[str | None] = mapped_column(Text)
    valor_extraido: Mapped[float | None] = mapped_column(Numeric(18, 2))
    status_leitura: Mapped[str] = mapped_column(String(30), default="PENDENTE")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    embarque: Mapped["Embarque"] = relationship(back_populates="documentos")


class RazaoLancamento(Base):
    """Lançamento importado do Razão Contábil enviado pelo usuário."""

    __tablename__ = "razao_lancamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    mes_referencia: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[date | None] = mapped_column(Date)
    empresa: Mapped[str | None] = mapped_column(String(120))
    conta_contabil: Mapped[str | None] = mapped_column(String(60))
    numero_contabil: Mapped[str | None] = mapped_column(String(60))
    unidade: Mapped[str | None] = mapped_column(String(60))
    historico: Mapped[str] = mapped_column(Text)
    processos_codigos: Mapped[list] = mapped_column(JSON, default=list)  # códigos extraídos do histórico
    documento_ref: Mapped[str | None] = mapped_column(String(120))
    valor_debito: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    valor_credito: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    categoria_classificada: Mapped[str | None] = mapped_column(String(60))
    rateio_aplicado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateioMatriz(Base):
    """Matriz Mestre de Rateio: percentual de um processo dentro de uma NF compartilhada."""

    __tablename__ = "rateio_matriz"

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"))
    nf_referencia: Mapped[str] = mapped_column(String(60), index=True)
    qtd_itens_processo: Mapped[int] = mapped_column()
    qtd_itens_total_nf: Mapped[int] = mapped_column()
    percentual: Mapped[float] = mapped_column(Numeric(9, 6))
    fonte: Mapped[str | None] = mapped_column(String(120))  # ex "Controle PIs"
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    processo: Mapped["Processo"] = relationship(back_populates="rateios")


class ComposicaoContabil(Base):
    """Composição contábil consolidada por categoria para um processo/mês."""

    __tablename__ = "composicao_contabil"

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"))
    mes_referencia: Mapped[date] = mapped_column(Date, index=True)
    categoria: Mapped[str] = mapped_column(String(60))
    valor_documentos: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    valor_contabilizado: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    valor_rateado: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    percentual_rateio: Mapped[float | None] = mapped_column(Numeric(9, 6))
    diferenca: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    processo: Mapped["Processo"] = relationship(back_populates="composicoes")


class RegraAprendida(Base):
    """Correção do usuário (classificação/rateio/natureza/documento) que passa a valer nas próximas análises."""

    __tablename__ = "regras_aprendidas"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40))  # classificacao, rateio, natureza, composicao, documento
    padrao: Mapped[str] = mapped_column(String(500))  # trecho do histórico / nome de arquivo / conta
    valor_corrigido: Mapped[str] = mapped_column(String(500))
    justificativa: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditoriaCalculo(Base):
    """Memória de cálculo completa e auditável de qualquer valor apresentado no sistema."""

    __tablename__ = "auditoria_calculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    referencia_tipo: Mapped[str] = mapped_column(String(40), index=True)  # rateio, composicao, fechamento
    referencia_id: Mapped[int] = mapped_column(index=True)
    memoria: Mapped[dict] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Fechamento(Base):
    """Resultado do fechamento contábil de um processo em um mês de referência."""

    __tablename__ = "fechamentos"
    __table_args__ = (UniqueConstraint("processo_id", "mes_referencia", name="uq_fechamento_processo_mes"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"))
    mes_referencia: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20))  # Fechado, Pendente, Bloqueado
    saldo_final: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    variacao_cambial: Mapped[float | None] = mapped_column(Numeric(18, 2))
    motivos_pendencia: Mapped[list] = mapped_column(JSON, default=list)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    processo: Mapped["Processo"] = relationship(back_populates="fechamentos")
