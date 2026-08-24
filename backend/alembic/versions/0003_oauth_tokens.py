"""Adiciona tabela para persistência de tokens OAuth

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-22

Tabela para armazenar tokens persistidos de integrações OAuth (Google Drive, etc.)
de forma segura no PostgreSQL, garantindo sobrevivência a restarts e deploys.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False, unique=True),
        sa.Column("token_data", sa.JSON(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_name", name="uq_oauth_tokens_service_name"),
    )
    op.create_index("ix_oauth_tokens_service_name", "oauth_tokens", ["service_name"])


def downgrade() -> None:
    op.drop_index("ix_oauth_tokens_service_name", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
