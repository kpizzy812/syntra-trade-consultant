"""merge_heads

Revision ID: e9044d387530
Revises: 7dbcfcab758d, e1b2c3d4f5a6
Create Date: 2025-11-27 22:14:37.849152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9044d387530'
down_revision: Union[str, Sequence[str], None] = ('7dbcfcab758d', 'e1b2c3d4f5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
