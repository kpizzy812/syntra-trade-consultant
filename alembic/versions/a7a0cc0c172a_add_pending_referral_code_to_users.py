"""add_pending_referral_code_to_users

Revision ID: a7a0cc0c172a
Revises: a351b18b5b44
Create Date: 2025-11-23 04:01:47.847109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7a0cc0c172a'
down_revision: Union[str, Sequence[str], None] = 'a351b18b5b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'pending_referral_code',
            sa.String(20),
            nullable=True,
            comment='Temporary storage for referral code until subscription verified'
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'pending_referral_code')
