"""add_startapp_param_to_users

Revision ID: 7444448bf4b0
Revises: 3378721a34ca
Create Date: 2025-12-09 14:48:52.242624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7444448bf4b0'
down_revision: Union[str, Sequence[str], None] = '3378721a34ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('startapp_param', sa.String(255), nullable=True))
    op.create_index('idx_users_startapp_param', 'users', ['startapp_param'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_users_startapp_param', table_name='users')
    op.drop_column('users', 'startapp_param')
