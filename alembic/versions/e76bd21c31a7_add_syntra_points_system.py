"""add_syntra_points_system

Revision ID: e76bd21c31a7
Revises: c96a01e68035
Create Date: 2025-12-03 02:11:56.868787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e76bd21c31a7'
down_revision: Union[str, Sequence[str], None] = 'c96a01e68035'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create points_levels table (configuration)
    op.create_table(
        'points_levels',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('level', sa.Integer(), nullable=False, comment='Level number (1, 2, 3, ...)'),
        sa.Column('name_ru', sa.String(length=100), nullable=False, comment='Level name in Russian'),
        sa.Column('name_en', sa.String(length=100), nullable=False, comment='Level name in English'),
        sa.Column('icon', sa.String(length=10), nullable=False, server_default='⭐', comment='Level icon (emoji)'),
        sa.Column('points_required', sa.Integer(), nullable=False, comment='Minimum lifetime_earned points to reach this level'),
        sa.Column('earning_multiplier', sa.Float(), nullable=False, server_default='1.0', comment='Points earning multiplier for this level'),
        sa.Column('description_ru', sa.Text(), nullable=True, comment='Level description in Russian'),
        sa.Column('description_en', sa.Text(), nullable=True, comment='Level description in English'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('level')
    )
    op.create_index(op.f('ix_points_levels_level'), 'points_levels', ['level'], unique=True)

    # Create points_balances table
    op.create_table(
        'points_balances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0', comment='Current $SYNTRA points balance'),
        sa.Column('lifetime_earned', sa.Integer(), nullable=False, server_default='0', comment='Total points earned (all time)'),
        sa.Column('lifetime_spent', sa.Integer(), nullable=False, server_default='0', comment='Total points spent (all time)'),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1', comment='User level (based on lifetime_earned)'),
        sa.Column('earning_multiplier', sa.Float(), nullable=False, server_default='1.0', comment='Points earning multiplier (1.0 = 100%, 1.5 = 150%)'),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0', comment='Current daily login streak'),
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0', comment='Longest daily login streak (all time)'),
        sa.Column('last_daily_login', sa.DateTime(timezone=True), nullable=True, comment='Last daily login timestamp'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(now() at time zone \'utc\')'), comment='Balance creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(now() at time zone \'utc\')'), comment='Balance last update timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_points_balances_user_id'), 'points_balances', ['user_id'], unique=True)

    # Create points_transactions table
    op.create_table(
        'points_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('balance_id', sa.Integer(), nullable=False, comment='Points balance ID (foreign key)'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (denormalized for fast queries)'),
        sa.Column('transaction_type', sa.String(length=50), nullable=False, comment='Transaction type (earn_*/spend_*/refund/expire)'),
        sa.Column('amount', sa.Integer(), nullable=False, comment='Points amount (positive for earn, negative for spend)'),
        sa.Column('balance_before', sa.Integer(), nullable=False, comment='Balance before transaction'),
        sa.Column('balance_after', sa.Integer(), nullable=False, comment='Balance after transaction'),
        sa.Column('description', sa.Text(), nullable=True, comment='Human-readable transaction description'),
        sa.Column('metadata_json', sa.Text(), nullable=True, comment='Additional metadata (JSON): request_id, payment_id, referral_id, etc.'),
        sa.Column('transaction_id', sa.String(length=255), nullable=True, comment='Unique transaction ID for idempotency (type:entity_id)'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='Expiration timestamp (NULL = never expires)'),
        sa.Column('is_expired', sa.Boolean(), nullable=False, server_default='false', comment='Is transaction expired (auto-processed)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(now() at time zone \'utc\')'), comment='Transaction timestamp'),
        sa.ForeignKeyConstraint(['balance_id'], ['points_balances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id')
    )
    op.create_index(op.f('ix_points_transactions_balance_id'), 'points_transactions', ['balance_id'])
    op.create_index(op.f('ix_points_transactions_user_id'), 'points_transactions', ['user_id'])
    op.create_index(op.f('ix_points_transactions_transaction_type'), 'points_transactions', ['transaction_type'])
    op.create_index(op.f('ix_points_transactions_transaction_id'), 'points_transactions', ['transaction_id'], unique=True)
    op.create_index(op.f('ix_points_transactions_expires_at'), 'points_transactions', ['expires_at'])
    op.create_index(op.f('ix_points_transactions_is_expired'), 'points_transactions', ['is_expired'])
    op.create_index(op.f('ix_points_transactions_created_at'), 'points_transactions', ['created_at'])

    # Insert default level configuration
    op.execute("""
        INSERT INTO points_levels (level, name_ru, name_en, icon, points_required, earning_multiplier, description_ru, description_en) VALUES
        (1, 'Новичок', 'Beginner', '🌱', 0, 1.0, 'Добро пожаловать в Syntra!', 'Welcome to Syntra!'),
        (2, 'Трейдер', 'Trader', '📈', 1000, 1.1, 'Вы начинаете разбираться в криптовалютах', 'You are starting to understand cryptocurrencies'),
        (3, 'Аналитик', 'Analyst', '🔍', 5000, 1.2, 'Вы умеете анализировать рынок', 'You know how to analyze the market'),
        (4, 'Эксперт', 'Expert', '⭐', 15000, 1.3, 'Вы - эксперт в техническом анализе', 'You are an expert in technical analysis'),
        (5, 'Мастер', 'Master', '💎', 50000, 1.5, 'Вы достигли мастерства в трейдинге', 'You have achieved mastery in trading'),
        (6, 'Легенда', 'Legend', '👑', 150000, 2.0, 'Легенда Syntra! Максимальный множитель', 'Syntra Legend! Maximum multiplier')
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_points_transactions_created_at'), table_name='points_transactions')
    op.drop_index(op.f('ix_points_transactions_is_expired'), table_name='points_transactions')
    op.drop_index(op.f('ix_points_transactions_expires_at'), table_name='points_transactions')
    op.drop_index(op.f('ix_points_transactions_transaction_id'), table_name='points_transactions')
    op.drop_index(op.f('ix_points_transactions_transaction_type'), table_name='points_transactions')
    op.drop_index(op.f('ix_points_transactions_user_id'), table_name='points_transactions')
    op.drop_index(op.f('ix_points_transactions_balance_id'), table_name='points_transactions')
    op.drop_table('points_transactions')

    op.drop_index(op.f('ix_points_balances_user_id'), table_name='points_balances')
    op.drop_table('points_balances')

    op.drop_index(op.f('ix_points_levels_level'), table_name='points_levels')
    op.drop_table('points_levels')
