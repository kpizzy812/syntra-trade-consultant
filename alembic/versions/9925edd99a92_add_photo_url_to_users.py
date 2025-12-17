"""add_photo_url_to_users

Revision ID: 9925edd99a92
Revises: e76bd21c31a7
Create Date: 2025-12-03 07:32:18.278524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9925edd99a92'
down_revision: Union[str, Sequence[str], None] = 'e76bd21c31a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add photo_url column to users table for avatar storage
    op.add_column('users', sa.Column('photo_url', sa.String(length=512), nullable=True, comment='User avatar URL (from Telegram or uploaded)'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'photo_url')
