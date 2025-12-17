"""add broadcast system

Revision ID: e1b2c3d4f5a6
Revises: f8a42c1b3e9d
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1b2c3d4f5a6'
down_revision: Union[str, None] = 'f8a42c1b3e9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create broadcast_templates table
    op.create_table(
        'broadcast_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False, comment='Template name for admin panel'),
        sa.Column('text', sa.Text(), nullable=True, comment='Message text content'),
        sa.Column('entities_json', sa.Text(), nullable=True, comment='Message entities as JSON'),
        sa.Column('media_type', sa.String(20), nullable=True, comment='Media type: photo, video, document, animation'),
        sa.Column('media_file_id', sa.String(255), nullable=True, comment='Telegram file_id for media'),
        sa.Column('buttons_json', sa.Text(), nullable=True, comment='Inline buttons as JSON'),
        sa.Column('target_audience', sa.String(30), nullable=False, default='all', comment='Target audience'),
        sa.Column('is_periodic', sa.Boolean(), nullable=False, default=False, comment='Is periodic template'),
        sa.Column('period_hours', sa.Integer(), nullable=True, comment='Period in hours'),
        sa.Column('next_send_at', sa.DateTime(timezone=True), nullable=True, comment='Next scheduled send time'),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True, comment='Last send timestamp'),
        sa.Column('status', sa.String(20), nullable=False, default='draft', comment='Template status'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='Is template active'),
        sa.Column('total_sent', sa.Integer(), nullable=False, default=0, comment='Total messages sent'),
        sa.Column('total_delivered', sa.Integer(), nullable=False, default=0, comment='Total messages delivered'),
        sa.Column('total_failed', sa.Integer(), nullable=False, default=0, comment='Total messages failed'),
        sa.Column('created_by', sa.BigInteger(), nullable=False, comment='Admin telegram_id who created template'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for broadcast_templates
    op.create_index('ix_broadcast_templates_target_audience', 'broadcast_templates', ['target_audience'])
    op.create_index('ix_broadcast_templates_next_send_at', 'broadcast_templates', ['next_send_at'])
    op.create_index('ix_broadcast_templates_status', 'broadcast_templates', ['status'])
    op.create_index('ix_broadcast_templates_is_active', 'broadcast_templates', ['is_active'])

    # Create broadcast_logs table
    op.create_table(
        'broadcast_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False, comment='Template ID (foreign key)'),
        sa.Column('total_recipients', sa.Integer(), nullable=False, default=0, comment='Total recipients count'),
        sa.Column('sent_count', sa.Integer(), nullable=False, default=0, comment='Successfully sent count'),
        sa.Column('failed_count', sa.Integer(), nullable=False, default=0, comment='Failed send count'),
        sa.Column('blocked_count', sa.Integer(), nullable=False, default=0, comment='Blocked by user count'),
        sa.Column('status', sa.String(20), nullable=False, default='sending', comment='Broadcast status'),
        sa.Column('errors_json', sa.Text(), nullable=True, comment='Errors as JSON array'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Broadcast completion timestamp'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['broadcast_templates.id'], ondelete='CASCADE')
    )

    # Create indexes for broadcast_logs
    op.create_index('ix_broadcast_logs_template_id', 'broadcast_logs', ['template_id'])
    op.create_index('ix_broadcast_logs_status', 'broadcast_logs', ['status'])
    op.create_index('ix_broadcast_logs_started_at', 'broadcast_logs', ['started_at'])


def downgrade() -> None:
    # Drop broadcast_logs table
    op.drop_index('ix_broadcast_logs_started_at', table_name='broadcast_logs')
    op.drop_index('ix_broadcast_logs_status', table_name='broadcast_logs')
    op.drop_index('ix_broadcast_logs_template_id', table_name='broadcast_logs')
    op.drop_table('broadcast_logs')

    # Drop broadcast_templates table
    op.drop_index('ix_broadcast_templates_is_active', table_name='broadcast_templates')
    op.drop_index('ix_broadcast_templates_status', table_name='broadcast_templates')
    op.drop_index('ix_broadcast_templates_next_send_at', table_name='broadcast_templates')
    op.drop_index('ix_broadcast_templates_target_audience', table_name='broadcast_templates')
    op.drop_table('broadcast_templates')
