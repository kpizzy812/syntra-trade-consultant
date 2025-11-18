"""make_subscription_id_nullable_in_payments

Revision ID: eebdf7a268e8
Revises: e1c5586ed73d
Create Date: 2025-11-18 00:47:36.326659

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eebdf7a268e8'
down_revision: Union[str, Sequence[str], None] = 'e1c5586ed73d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make subscription_id nullable in payments table
    op.alter_column('payments', 'subscription_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Make subscription_id NOT NULL again
    op.alter_column('payments', 'subscription_id',
                    existing_type=sa.Integer(),
                    nullable=False)
