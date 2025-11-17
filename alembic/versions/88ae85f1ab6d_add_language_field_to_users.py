"""add_language_field_to_users

Revision ID: 88ae85f1ab6d
Revises: 2e5903c1536e
Create Date: 2025-11-17 03:47:09.053625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88ae85f1ab6d'
down_revision: Union[str, Sequence[str], None] = '2e5903c1536e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add language column to users table
    op.add_column('users', sa.Column('language', sa.String(length=10), nullable=False, server_default='ru', comment='User language preference (ru, en)'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove language column from users table
    op.drop_column('users', 'language')
