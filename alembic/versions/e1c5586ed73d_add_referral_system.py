"""add_referral_system

Revision ID: e1c5586ed73d
Revises: 3818b6add546
Create Date: 2025-11-17 20:17:27.451697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1c5586ed73d'
down_revision: Union[str, Sequence[str], None] = '3818b6add546'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add referral fields to users table
    op.add_column('users', sa.Column('referral_code', sa.String(length=20), nullable=True, comment='Unique referral code for this user'))
    op.add_column('users', sa.Column('referred_by_id', sa.Integer(), nullable=True, comment='ID of user who referred this user'))
    op.create_index(op.f('ix_users_referral_code'), 'users', ['referral_code'], unique=True)
    op.create_index(op.f('ix_users_referred_by_id'), 'users', ['referred_by_id'], unique=False)
    op.create_foreign_key('fk_users_referred_by', 'users', 'users', ['referred_by_id'], ['id'], ondelete='SET NULL')

    # Create referrals table
    op.create_table('referrals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=False, comment='User ID who referred (foreign key)'),
        sa.Column('referee_id', sa.Integer(), nullable=False, comment='User ID who was referred (foreign key)'),
        sa.Column('referral_code', sa.String(length=20), nullable=False, comment='Referral code used'),
        sa.Column('status', sa.String(length=20), nullable=False, comment='Status: pending, active, churned'),
        sa.Column('trial_granted', sa.Boolean(), nullable=False, comment='Has trial been granted to referee'),
        sa.Column('bonus_granted', sa.Boolean(), nullable=False, comment='Has bonus been granted to referrer'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Referral creation timestamp'),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True, comment='When referral became active'),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['referee_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('referrer_id', 'referee_id', name='uq_referrer_referee')
    )
    op.create_index(op.f('ix_referrals_referrer_id'), 'referrals', ['referrer_id'], unique=False)
    op.create_index(op.f('ix_referrals_referee_id'), 'referrals', ['referee_id'], unique=False)
    op.create_index(op.f('ix_referrals_status'), 'referrals', ['status'], unique=False)
    op.create_index(op.f('ix_referrals_referral_code'), 'referrals', ['referral_code'], unique=False)

    # Create bonus_requests table
    op.create_table('bonus_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),
        sa.Column('amount', sa.Integer(), nullable=False, comment='Number of bonus requests'),
        sa.Column('source', sa.String(length=50), nullable=False, comment='Source: referral_signup, tier_monthly, challenge, achievement, admin_grant'),
        sa.Column('description', sa.Text(), nullable=True, comment='Description of bonus'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='Expiration date (NULL = never expires)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Bonus creation timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bonus_requests_user_id'), 'bonus_requests', ['user_id'], unique=False)
    op.create_index(op.f('ix_bonus_requests_source'), 'bonus_requests', ['source'], unique=False)
    op.create_index(op.f('ix_bonus_requests_expires_at'), 'bonus_requests', ['expires_at'], unique=False)

    # Create referral_tiers table
    op.create_table('referral_tiers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),
        sa.Column('tier', sa.String(length=20), nullable=False, comment='Tier: bronze, silver, gold, platinum'),
        sa.Column('total_referrals', sa.Integer(), nullable=False, comment='Total number of referrals (all time)'),
        sa.Column('active_referrals', sa.Integer(), nullable=False, comment='Number of active referrals'),
        sa.Column('monthly_bonus', sa.Integer(), nullable=False, comment='Monthly bonus requests for this tier'),
        sa.Column('discount_percent', sa.Integer(), nullable=False, comment='Discount percentage on subscriptions'),
        sa.Column('revenue_share_percent', sa.Numeric(precision=5, scale=2), nullable=False, comment='Revenue share percentage (0-100)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Tier creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, comment='Tier last update timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_referral_tiers_user_id'), 'referral_tiers', ['user_id'], unique=True)
    op.create_index(op.f('ix_referral_tiers_tier'), 'referral_tiers', ['tier'], unique=False)
    op.create_index(op.f('ix_referral_tiers_active_referrals'), 'referral_tiers', ['active_referrals'], unique=False)

    # Create referral_balances table
    op.create_table('referral_balances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),
        sa.Column('balance_usd', sa.Numeric(precision=10, scale=2), nullable=False, comment='Current balance in USD'),
        sa.Column('earned_total_usd', sa.Numeric(precision=10, scale=2), nullable=False, comment='Total earned (all time)'),
        sa.Column('withdrawn_total_usd', sa.Numeric(precision=10, scale=2), nullable=False, comment='Total withdrawn (all time)'),
        sa.Column('spent_total_usd', sa.Numeric(precision=10, scale=2), nullable=False, comment='Total spent on subscriptions (all time)'),
        sa.Column('last_payout_at', sa.DateTime(timezone=True), nullable=True, comment='Last revenue share payout timestamp'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Balance creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, comment='Balance last update timestamp'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_referral_balances_user_id'), 'referral_balances', ['user_id'], unique=True)

    # Create balance_transactions table
    op.create_table('balance_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('balance_id', sa.Integer(), nullable=False, comment='Balance ID (foreign key)'),
        sa.Column('type', sa.String(length=20), nullable=False, comment='Type: earn, withdraw, spend, refund'),
        sa.Column('amount_usd', sa.Numeric(precision=10, scale=2), nullable=False, comment='Transaction amount in USD'),
        sa.Column('description', sa.Text(), nullable=True, comment='Transaction description'),
        sa.Column('withdrawal_address', sa.String(length=255), nullable=True, comment='TON wallet address for withdrawals'),
        sa.Column('withdrawal_hash', sa.String(length=255), nullable=True, comment='Blockchain transaction hash'),
        sa.Column('withdrawal_status', sa.String(length=20), nullable=True, comment='Withdrawal status: pending, completed, failed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='Transaction creation timestamp'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Transaction completion timestamp'),
        sa.ForeignKeyConstraint(['balance_id'], ['referral_balances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_balance_transactions_balance_id'), 'balance_transactions', ['balance_id'], unique=False)
    op.create_index(op.f('ix_balance_transactions_type'), 'balance_transactions', ['type'], unique=False)
    op.create_index(op.f('ix_balance_transactions_withdrawal_status'), 'balance_transactions', ['withdrawal_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop balance_transactions table
    op.drop_index(op.f('ix_balance_transactions_withdrawal_status'), table_name='balance_transactions')
    op.drop_index(op.f('ix_balance_transactions_type'), table_name='balance_transactions')
    op.drop_index(op.f('ix_balance_transactions_balance_id'), table_name='balance_transactions')
    op.drop_table('balance_transactions')

    # Drop referral_balances table
    op.drop_index(op.f('ix_referral_balances_user_id'), table_name='referral_balances')
    op.drop_table('referral_balances')

    # Drop referral_tiers table
    op.drop_index(op.f('ix_referral_tiers_active_referrals'), table_name='referral_tiers')
    op.drop_index(op.f('ix_referral_tiers_tier'), table_name='referral_tiers')
    op.drop_index(op.f('ix_referral_tiers_user_id'), table_name='referral_tiers')
    op.drop_table('referral_tiers')

    # Drop bonus_requests table
    op.drop_index(op.f('ix_bonus_requests_expires_at'), table_name='bonus_requests')
    op.drop_index(op.f('ix_bonus_requests_source'), table_name='bonus_requests')
    op.drop_index(op.f('ix_bonus_requests_user_id'), table_name='bonus_requests')
    op.drop_table('bonus_requests')

    # Drop referrals table
    op.drop_index(op.f('ix_referrals_referral_code'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_status'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referee_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referrer_id'), table_name='referrals')
    op.drop_table('referrals')

    # Remove referral fields from users table
    op.drop_constraint('fk_users_referred_by', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_referred_by_id'), table_name='users')
    op.drop_index(op.f('ix_users_referral_code'), table_name='users')
    op.drop_column('users', 'referred_by_id')
    op.drop_column('users', 'referral_code')
