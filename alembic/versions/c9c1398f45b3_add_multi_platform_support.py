"""add_multi_platform_support

Revision ID: c9c1398f45b3
Revises: 76103a2bba85
Create Date: 2025-11-25 07:00:32.008799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9c1398f45b3'
down_revision: Union[str, Sequence[str], None] = '76103a2bba85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add multi-platform support to users table.

    Changes:
    1. Make telegram_id nullable (for web users)
    2. Add email field (unique, nullable)
    3. Add email_verified field
    4. Add registration_platform field (telegram/web/ios/android)
    """
    # Add new columns
    op.add_column('users', sa.Column(
        'email',
        sa.String(255),
        nullable=True,
        comment='User email for web registration'
    ))
    op.add_column('users', sa.Column(
        'email_verified',
        sa.Boolean(),
        nullable=False,
        server_default='false',
        comment='Email verification status'
    ))
    op.add_column('users', sa.Column(
        'registration_platform',
        sa.String(20),
        nullable=False,
        server_default='telegram',
        comment='Platform where user registered (telegram/web/ios/android)'
    ))

    # Create index and unique constraint on email
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Make telegram_id nullable (for web users)
    # Note: Existing users will keep their telegram_id
    op.alter_column('users', 'telegram_id',
                    existing_type=sa.BigInteger(),
                    nullable=True)

    # Set registration_platform to 'telegram' for all existing users
    # (this is already set by server_default, but being explicit)
    op.execute("UPDATE users SET registration_platform = 'telegram' WHERE registration_platform IS NULL")


def downgrade() -> None:
    """
    Remove multi-platform support (rollback).

    WARNING: This will delete email and registration_platform data!
    """
    # Drop new columns
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'registration_platform')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'email')

    # Make telegram_id NOT NULL again
    # WARNING: This will fail if there are web users without telegram_id
    op.alter_column('users', 'telegram_id',
                    existing_type=sa.BigInteger(),
                    nullable=False)
