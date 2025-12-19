"""add_paper_fields_to_class_stats

Revision ID: b2c3d4e5f6g8
Revises: a1b2c3d4e5f7
Create Date: 2025-12-19 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add paper trading fields to scenario_class_stats."""

    # Paper trade counts
    op.add_column('scenario_class_stats', sa.Column(
        'paper_entered',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='Кол-во paper trades (entered)'
    ))
    op.add_column('scenario_class_stats', sa.Column(
        'paper_wins',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='Кол-во paper wins'
    ))
    op.add_column('scenario_class_stats', sa.Column(
        'paper_losses',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='Кол-во paper losses'
    ))

    # Paper metrics
    op.add_column('scenario_class_stats', sa.Column(
        'paper_ev_r',
        sa.Float(),
        nullable=True,
        comment='Средний realized R от paper trades'
    ))
    op.add_column('scenario_class_stats', sa.Column(
        'paper_wr',
        sa.Float(),
        nullable=True,
        comment='Paper winrate'
    ))
    op.add_column('scenario_class_stats', sa.Column(
        'paper_mae_r_avg',
        sa.Float(),
        nullable=True,
        comment='Avg MAE R от paper trades'
    ))
    op.add_column('scenario_class_stats', sa.Column(
        'paper_mfe_r_avg',
        sa.Float(),
        nullable=True,
        comment='Avg MFE R от paper trades'
    ))
    op.add_column('scenario_class_stats', sa.Column(
        'paper_last_updated',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='Последнее обновление paper stats'
    ))


def downgrade() -> None:
    """Remove paper trading fields from scenario_class_stats."""
    op.drop_column('scenario_class_stats', 'paper_last_updated')
    op.drop_column('scenario_class_stats', 'paper_mfe_r_avg')
    op.drop_column('scenario_class_stats', 'paper_mae_r_avg')
    op.drop_column('scenario_class_stats', 'paper_wr')
    op.drop_column('scenario_class_stats', 'paper_ev_r')
    op.drop_column('scenario_class_stats', 'paper_losses')
    op.drop_column('scenario_class_stats', 'paper_wins')
    op.drop_column('scenario_class_stats', 'paper_entered')
