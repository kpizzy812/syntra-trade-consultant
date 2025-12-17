"""add_privacy_policy_shown_to_users

Revision ID: a351b18b5b44
Revises: f8a42c1b3e9d
Create Date: 2025-11-23 03:06:59.681301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a351b18b5b44'
down_revision: Union[str, Sequence[str], None] = 'f8a42c1b3e9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('privacy_policy_shown', sa.Boolean(), nullable=False, server_default='false',
                  comment='Flag indicating if privacy policy was shown to user')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'privacy_policy_shown')
