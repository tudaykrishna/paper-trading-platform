"""add instruments.category

Revision ID: 0002_instrument_category
Revises: 0001_initial
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_instrument_category"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("category", sa.String(20), nullable=False, server_default="OTHER"),
    )
    op.create_index("ix_instruments_category", "instruments", ["category"])


def downgrade() -> None:
    op.drop_index("ix_instruments_category", table_name="instruments")
    op.drop_column("instruments", "category")
