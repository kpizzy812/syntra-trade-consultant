"""merge_scenario_class_stats_heads

Revision ID: 9f5ed61d59b1
Revises: c3d4e5f6a7b8, f1a2b3c4d5e6
Create Date: 2025-12-17 13:25:38.092153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f5ed61d59b1'
down_revision: Union[str, Sequence[str], None] = ('c3d4e5f6a7b8', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
