"""mekanik_test_kabul_kriterleri

Revision ID: e10eec6ff9ba
Revises: bd1f11a385bf
Create Date: 2026-09-02 18:36:32.165782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e10eec6ff9ba'
down_revision: Union[str, None] = 'bd1f11a385bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'packaging_requests',
        sa.Column('mechanical_test_criteria', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('packaging_requests', 'mechanical_test_criteria')
