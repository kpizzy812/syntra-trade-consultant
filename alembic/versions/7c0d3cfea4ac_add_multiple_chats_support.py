"""add_multiple_chats_support

Revision ID: 7c0d3cfea4ac
Revises: 548573fe410b
Create Date: 2025-11-25 10:16:52.851273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c0d3cfea4ac'
down_revision: Union[str, Sequence[str], None] = '548573fe410b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add support for multiple chats (like ChatGPT)

    Creates:
    - chats table (chat sessions)
    - chat_messages table (messages within chats)

    Keeps chat_history table for backward compatibility
    """
    # Create chats table
    op.create_table(
        'chats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),
        sa.Column('title', sa.String(length=255), nullable=False, comment='Chat title (auto-generated from first message)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Chat creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, comment='Last message timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Chat sessions (like ChatGPT conversations)'
    )
    op.create_index(op.f('ix_chats_user_id'), 'chats', ['user_id'], unique=False)

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=False, comment='Chat ID (foreign key)'),
        sa.Column('role', sa.String(length=50), nullable=False, comment='Message role: user, assistant, system'),
        sa.Column('content', sa.Text(), nullable=False, comment='Message content'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, comment='Message timestamp'),
        sa.Column('tokens_used', sa.Integer(), nullable=True, comment='Tokens used (for AI responses)'),
        sa.Column('model', sa.String(length=100), nullable=True, comment='AI model used (gpt-4o, gpt-4o-mini, etc.)'),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Messages within chat sessions'
    )
    op.create_index(op.f('ix_chat_messages_chat_id'), 'chat_messages', ['chat_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_timestamp'), 'chat_messages', ['timestamp'], unique=False)


def downgrade() -> None:
    """
    Remove multiple chats support

    WARNING: This will delete all chat data!
    """
    # Drop tables in reverse order (messages first, then chats)
    op.drop_index(op.f('ix_chat_messages_timestamp'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_chat_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index(op.f('ix_chats_user_id'), table_name='chats')
    op.drop_table('chats')
