"""Add asset mapping table and update normalized schema

Revision ID: 0003_add_asset_mapping
Revises: 0002_add_raw_csv
Create Date: 2025-12-26

This migration adds:
1. asset_mappings table for cross-source entity unification
2. coingecko_id and coinpaprika_id columns to normalized_crypto_assets
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_asset_mapping'
down_revision = '0002_add_raw_csv'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create asset_mappings table for cross-source entity unification
    op.create_table(
        'asset_mappings',
        sa.Column('asset_uid', sa.String(100), primary_key=True, comment='Canonical unified asset identifier'),
        sa.Column('coingecko_id', sa.String(100), nullable=True, unique=True, comment='CoinGecko API identifier'),
        sa.Column('coinpaprika_id', sa.String(100), nullable=True, unique=True, comment='CoinPaprika API identifier'),
        sa.Column('symbol', sa.String(20), nullable=False, comment='Trading symbol'),
        sa.Column('name', sa.String(200), nullable=False, comment='Canonical asset name'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create indexes for asset_mappings
    op.create_index('ix_asset_mappings_asset_uid', 'asset_mappings', ['asset_uid'])
    op.create_index('ix_asset_mappings_coingecko_id', 'asset_mappings', ['coingecko_id'])
    op.create_index('ix_asset_mappings_coinpaprika_id', 'asset_mappings', ['coinpaprika_id'])
    op.create_index('ix_asset_mappings_symbol', 'asset_mappings', ['symbol'])
    op.create_index('ix_asset_mapping_symbol_name', 'asset_mappings', ['symbol', 'name'])
    
    # Add source-specific ID columns to normalized_crypto_assets
    op.add_column(
        'normalized_crypto_assets',
        sa.Column('coingecko_id', sa.String(100), nullable=True, comment='Original CoinGecko identifier')
    )
    op.add_column(
        'normalized_crypto_assets',
        sa.Column('coinpaprika_id', sa.String(100), nullable=True, comment='Original CoinPaprika identifier')
    )
    
    # Create indexes for the new columns
    op.create_index('ix_normalized_crypto_assets_coingecko_id', 'normalized_crypto_assets', ['coingecko_id'])
    op.create_index('ix_normalized_crypto_assets_coinpaprika_id', 'normalized_crypto_assets', ['coinpaprika_id'])


def downgrade() -> None:
    # Remove indexes from normalized_crypto_assets
    op.drop_index('ix_normalized_crypto_assets_coinpaprika_id', 'normalized_crypto_assets')
    op.drop_index('ix_normalized_crypto_assets_coingecko_id', 'normalized_crypto_assets')
    
    # Remove source-specific ID columns from normalized_crypto_assets
    op.drop_column('normalized_crypto_assets', 'coinpaprika_id')
    op.drop_column('normalized_crypto_assets', 'coingecko_id')
    
    # Drop asset_mappings table indexes
    op.drop_index('ix_asset_mapping_symbol_name', 'asset_mappings')
    op.drop_index('ix_asset_mappings_symbol', 'asset_mappings')
    op.drop_index('ix_asset_mappings_coinpaprika_id', 'asset_mappings')
    op.drop_index('ix_asset_mappings_coingecko_id', 'asset_mappings')
    op.drop_index('ix_asset_mappings_asset_uid', 'asset_mappings')
    
    # Drop asset_mappings table
    op.drop_table('asset_mappings')
