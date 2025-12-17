"""add_separate_limits_and_trial_discount

Revision ID: 76103a2bba85
Revises: a7a0cc0c172a
Create Date: 2025-11-25 05:55:19.475326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76103a2bba85'
down_revision: Union[str, Sequence[str], None] = 'a7a0cc0c172a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add separate request counters to request_limits table
    op.add_column('request_limits', sa.Column('text_count', sa.Integer(), nullable=False, server_default='0', comment='Number of text requests made today'))
    op.add_column('request_limits', sa.Column('chart_count', sa.Integer(), nullable=False, server_default='0', comment='Number of chart requests made today'))
    op.add_column('request_limits', sa.Column('vision_count', sa.Integer(), nullable=False, server_default='0', comment='Number of vision requests made today'))

    # Add post-trial discount fields to subscriptions table
    op.add_column('subscriptions', sa.Column('has_post_trial_discount', sa.Boolean(), nullable=False, server_default='false', comment='User is eligible for post-trial discount (-20%)'))
    op.add_column('subscriptions', sa.Column('discount_expires_at', sa.DateTime(timezone=True), nullable=True, comment='Post-trial discount expiration (48h after trial ends)'))
    op.add_column('subscriptions', sa.Column('trial_notified_24h', sa.Boolean(), nullable=False, server_default='false', comment='24h trial ending notification sent'))
    op.add_column('subscriptions', sa.Column('trial_notified_end', sa.Boolean(), nullable=False, server_default='false', comment='Trial ended notification sent'))

    # Create index on discount_expires_at for efficient cron queries
    op.create_index('ix_subscriptions_discount_expires_at', 'subscriptions', ['discount_expires_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index
    op.drop_index('ix_subscriptions_discount_expires_at', table_name='subscriptions')

    # Drop post-trial discount fields from subscriptions
    op.drop_column('subscriptions', 'trial_notified_end')
    op.drop_column('subscriptions', 'trial_notified_24h')
    op.drop_column('subscriptions', 'discount_expires_at')
    op.drop_column('subscriptions', 'has_post_trial_discount')

    # Drop separate request counters from request_limits
    op.drop_column('request_limits', 'vision_count')
    op.drop_column('request_limits', 'chart_count')
    op.drop_column('request_limits', 'text_count')
