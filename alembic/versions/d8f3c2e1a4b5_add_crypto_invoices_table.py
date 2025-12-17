"""Add crypto_invoices table for CryptoBot payments

Revision ID: d8f3c2e1a4b5
Revises: 7c0d3cfea4ac
Create Date: 2025-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f3c2e1a4b5'
down_revision: Union[str, None] = '7c0d3cfea4ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create crypto_invoices table for CryptoBot payments"""
    op.create_table(
        'crypto_invoices',
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # User reference
        sa.Column('user_id', sa.Integer(), nullable=False, comment='User ID (foreign key)'),

        # CryptoBot invoice data
        sa.Column('invoice_id', sa.BigInteger(), nullable=False, comment='Invoice ID from CryptoBot API'),
        sa.Column('hash', sa.String(255), nullable=False, comment='Invoice hash from CryptoBot'),

        # Amount and currency
        sa.Column('amount_usd', sa.Float(), nullable=False, comment='Amount in USD'),
        sa.Column('asset', sa.String(20), nullable=False, comment='Cryptocurrency (USDT, TON, BTC, etc.)'),
        sa.Column('amount_crypto', sa.Float(), nullable=False, comment='Amount in cryptocurrency'),

        # Subscription info
        sa.Column('tier', sa.String(20), nullable=False, comment='Subscription tier: basic, premium, vip'),
        sa.Column('duration_months', sa.Integer(), nullable=False, comment='Subscription duration in months'),

        # Status and dates
        sa.Column('status', sa.String(20), nullable=False, server_default='active', comment='Invoice status: active, paid, expired, cancelled'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Invoice creation timestamp'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='Invoice expiration timestamp'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True, comment='Payment timestamp'),

        # Payment URLs
        sa.Column('bot_invoice_url', sa.String(500), nullable=False, comment='URL to pay via @CryptoBot'),
        sa.Column('mini_app_invoice_url', sa.String(500), nullable=True, comment='URL for Mini App payment (API 1.4+)'),
        sa.Column('web_app_invoice_url', sa.String(500), nullable=True, comment='URL for Web payment (API 1.4+)'),

        # Payment details (filled after payment)
        sa.Column('paid_asset', sa.String(20), nullable=True, comment='Asset used for payment (may differ)'),
        sa.Column('paid_amount', sa.Float(), nullable=True, comment='Actual paid amount'),
        sa.Column('paid_usd_rate', sa.Float(), nullable=True, comment='USD exchange rate at payment time'),
        sa.Column('fee_amount', sa.Float(), nullable=True, comment='CryptoBot fee amount'),
        sa.Column('fee_asset', sa.String(20), nullable=True, comment='Fee asset'),
        sa.Column('paid_anonymously', sa.Boolean(), nullable=False, server_default='false', comment='Paid anonymously (API 1.4)'),

        # Additional data
        sa.Column('payload', sa.Text(), nullable=True, comment='Custom payload data (JSON string)'),
        sa.Column('comment', sa.Text(), nullable=True, comment='User comment from payment'),

        # Processing flag
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false', comment='Whether subscription was activated'),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign key
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('ix_crypto_invoices_user_id', 'crypto_invoices', ['user_id'])
    op.create_index('ix_crypto_invoices_invoice_id', 'crypto_invoices', ['invoice_id'], unique=True)
    op.create_index('ix_crypto_invoices_hash', 'crypto_invoices', ['hash'], unique=True)
    op.create_index('ix_crypto_invoices_status', 'crypto_invoices', ['status'])
    op.create_index('ix_crypto_invoices_created_at', 'crypto_invoices', ['created_at'])
    op.create_index('ix_crypto_invoices_expires_at', 'crypto_invoices', ['expires_at'])
    op.create_index('ix_crypto_invoices_processed', 'crypto_invoices', ['processed'])


def downgrade() -> None:
    """Drop crypto_invoices table"""
    # Drop indexes first
    op.drop_index('ix_crypto_invoices_processed', 'crypto_invoices')
    op.drop_index('ix_crypto_invoices_expires_at', 'crypto_invoices')
    op.drop_index('ix_crypto_invoices_created_at', 'crypto_invoices')
    op.drop_index('ix_crypto_invoices_status', 'crypto_invoices')
    op.drop_index('ix_crypto_invoices_hash', 'crypto_invoices')
    op.drop_index('ix_crypto_invoices_invoice_id', 'crypto_invoices')
    op.drop_index('ix_crypto_invoices_user_id', 'crypto_invoices')

    # Drop table
    op.drop_table('crypto_invoices')
