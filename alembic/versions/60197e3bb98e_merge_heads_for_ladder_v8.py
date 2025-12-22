"""merge heads for ladder v8

Revision ID: 60197e3bb98e
Revises: c3d4e5f6g7h9, l4dd3r_v8
Create Date: 2025-12-22 12:01:41.714096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60197e3bb98e'
down_revision: Union[str, Sequence[str], None] = ('c3d4e5f6g7h9', 'l4dd3r_v8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
