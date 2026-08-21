"""schema inicial

Revision ID: 0001
Revises:
Create Date: 2026-07-24

Escrita à mão (não via --autogenerate) porque não há Postgres acessível nesta
máquina para introspecção; espelha app/infrastructure/db/models.py exatamente.
Confirme rodando `alembic upgrade head` no primeiro `docker compose up`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(10), nullable=False, unique=True),
        sa.Column("nome", sa.String(120), nullable=False),
    )

    op.create_table(
        "processos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("fornecedor", sa.String(255), nullable=True),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("drive_folder_id", sa.String(120), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo", name="uq_processo_codigo"),
    )
    op.create_index("ix_processos_codigo", "processos", ["codigo"])

    op.create_table(
        "embarques",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "processo_id",
            sa.Integer(),
            sa.ForeignKey("processos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("trading", sa.String(120), nullable=True),
        sa.Column("referencia_trading", sa.String(120), nullable=True),
        sa.Column("drive_folder_id", sa.String(120), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("processo_id", "codigo", name="uq_embarque_codigo"),
    )
    op.create_index("ix_embarques_codigo", "embarques", ["codigo"])

    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "embarque_id",
            sa.Integer(),
            sa.ForeignKey("embarques.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("drive_file_id", sa.String(120), nullable=False),
        sa.Column("nome_arquivo", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("texto_extraido", sa.Text(), nullable=True),
        sa.Column("valor_extraido", sa.Numeric(18, 2), nullable=True),
        sa.Column("status_leitura", sa.String(30), nullable=False, server_default="PENDENTE"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documentos_tipo", "documentos", ["tipo"])

    op.create_table(
        "razao_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mes_referencia", sa.Date(), nullable=False),
        sa.Column("empresa", sa.String(120), nullable=True),
        sa.Column("conta_contabil", sa.String(60), nullable=True),
        sa.Column("historico", sa.Text(), nullable=False),
        sa.Column("processos_codigos", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("documento_ref", sa.String(120), nullable=True),
        sa.Column("valor_debito", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("valor_credito", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("categoria_classificada", sa.String(60), nullable=True),
        sa.Column("rateio_aplicado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_razao_lancamentos_mes_referencia", "razao_lancamentos", ["mes_referencia"])

    op.create_table(
        "rateio_matriz",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("processo_id", sa.Integer(), sa.ForeignKey("processos.id"), nullable=False),
        sa.Column("nf_referencia", sa.String(60), nullable=False),
        sa.Column("qtd_itens_processo", sa.Integer(), nullable=False),
        sa.Column("qtd_itens_total_nf", sa.Integer(), nullable=False),
        sa.Column("percentual", sa.Numeric(9, 6), nullable=False),
        sa.Column("fonte", sa.String(120), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rateio_matriz_nf_referencia", "rateio_matriz", ["nf_referencia"])

    op.create_table(
        "composicao_contabil",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("processo_id", sa.Integer(), sa.ForeignKey("processos.id"), nullable=False),
        sa.Column("mes_referencia", sa.Date(), nullable=False),
        sa.Column("categoria", sa.String(60), nullable=False),
        sa.Column("valor_documentos", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("valor_contabilizado", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("valor_rateado", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("percentual_rateio", sa.Numeric(9, 6), nullable=True),
        sa.Column("diferenca", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_composicao_contabil_mes_referencia", "composicao_contabil", ["mes_referencia"])

    op.create_table(
        "regras_aprendidas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("padrao", sa.String(500), nullable=False),
        sa.Column("valor_corrigido", sa.String(500), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.Column("criado_por", sa.String(255), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "auditoria_calculo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referencia_tipo", sa.String(40), nullable=False),
        sa.Column("referencia_id", sa.Integer(), nullable=False),
        sa.Column("memoria", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auditoria_calculo_referencia_tipo", "auditoria_calculo", ["referencia_tipo"])
    op.create_index("ix_auditoria_calculo_referencia_id", "auditoria_calculo", ["referencia_id"])

    op.create_table(
        "fechamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("processo_id", sa.Integer(), sa.ForeignKey("processos.id"), nullable=False),
        sa.Column("mes_referencia", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("saldo_final", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("variacao_cambial", sa.Numeric(18, 2), nullable=True),
        sa.Column("motivos_pendencia", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("processo_id", "mes_referencia", name="uq_fechamento_processo_mes"),
    )
    op.create_index("ix_fechamentos_mes_referencia", "fechamentos", ["mes_referencia"])


def downgrade() -> None:
    op.drop_table("fechamentos")
    op.drop_table("auditoria_calculo")
    op.drop_table("regras_aprendidas")
    op.drop_table("composicao_contabil")
    op.drop_table("rateio_matriz")
    op.drop_table("razao_lancamentos")
    op.drop_table("documentos")
    op.drop_table("embarques")
    op.drop_table("processos")
    op.drop_table("empresas")
