"""add mode_id and mode_family to scenario_snapshots

Revision ID: d1e2f3a4b5c6
Revises: 9f5ed61d59b1
Create Date: 2024-12-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = '9f5ed61d59b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'scenario_snapshots',
        sa.Column(
            'mode_id',
            sa.String(20),
            nullable=True,
            server_default='standard',
            comment='Trading mode: conservative, standard, high_risk, meme'
        )
    )

    op.add_column(
        'scenario_snapshots',
        sa.Column(
            'mode_family',
            sa.String(20),
            nullable=True,
            server_default='balanced',
            comment='Mode family: cautious, balanced, speculative'
        )
    )


def downgrade() -> None:
    op.drop_column('scenario_snapshots', 'mode_family')
    op.drop_column('scenario_snapshots', 'mode_id')
