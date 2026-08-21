"""adiciona data/unidade/numero_contabil ao razão

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-26

Necessário para replicar as colunas reais de 'Importações em Andamento' /
'Processos Fechados' (planilhas de controle manual da equipe) na exportação
de linhas rateadas.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("razao_lancamentos", sa.Column("data", sa.Date(), nullable=True))
    op.add_column("razao_lancamentos", sa.Column("numero_contabil", sa.String(60), nullable=True))
    op.add_column("razao_lancamentos", sa.Column("unidade", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("razao_lancamentos", "unidade")
    op.drop_column("razao_lancamentos", "numero_contabil")
    op.drop_column("razao_lancamentos", "data")
