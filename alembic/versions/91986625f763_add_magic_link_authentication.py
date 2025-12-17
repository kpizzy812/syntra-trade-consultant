"""add_magic_link_authentication

Revision ID: 91986625f763
Revises: c9c1398f45b3
Create Date: 2025-11-25 08:58:23.768603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91986625f763'
down_revision: Union[str, Sequence[str], None] = 'c9c1398f45b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add magic_links table for passwordless email authentication."""
    op.create_table(
        'magic_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False, comment='Email address for magic link'),
        sa.Column('token', sa.String(255), nullable=False, comment='Unique magic link token (URL-safe random)'),
        sa.Column('user_id', sa.Integer(), nullable=True, comment='User ID if already registered'),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='false', comment='Has this token been used (single-use enforcement)'),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True, comment='When token was used'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, comment='Token expiration time (15 minutes from creation)'),
        sa.Column('request_ip', sa.String(45), nullable=True, comment='IP address that requested magic link'),
        sa.Column('used_ip', sa.String(45), nullable=True, comment='IP address that used magic link'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Token creation timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )

    # Create indexes
    op.create_index('ix_magic_links_email', 'magic_links', ['email'])
    op.create_index('ix_magic_links_token', 'magic_links', ['token'], unique=True)
    op.create_index('ix_magic_links_user_id', 'magic_links', ['user_id'])
    op.create_index('ix_magic_links_expires_at', 'magic_links', ['expires_at'])


def downgrade() -> None:
    """Remove magic_links table."""
    op.drop_index('ix_magic_links_expires_at', table_name='magic_links')
    op.drop_index('ix_magic_links_user_id', table_name='magic_links')
    op.drop_index('ix_magic_links_token', table_name='magic_links')
    op.drop_index('ix_magic_links_email', table_name='magic_links')
    op.drop_table('magic_links')
