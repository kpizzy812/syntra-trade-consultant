"""add epoch field to forward_test_snapshots

Revision ID: f42418e04617
Revises: unr34l1z3d
Create Date: 2025-12-22 20:12:03.591831

Epoch field для разделения данных на эпохи.
epoch=0 означает скрытые/невалидные данные.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f42418e04617'
down_revision: Union[str, Sequence[str], None] = 'unr34l1z3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add epoch field to forward_test_snapshots."""
    op.add_column(
        'forward_test_snapshots',
        sa.Column(
            'epoch',
            sa.Integer(),
            server_default=sa.text('1'),
            nullable=False,
            comment='Эпоха данных (0 = скрытые/невалидные)'
        )
    )
    op.create_index('ix_snapshot_epoch', 'forward_test_snapshots', ['epoch'])


def downgrade() -> None:
    """Remove epoch field from forward_test_snapshots."""
    op.drop_index('ix_snapshot_epoch', table_name='forward_test_snapshots')
    op.drop_column('forward_test_snapshots', 'epoch')
