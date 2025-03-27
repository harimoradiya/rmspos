"""add restaurant chain tables

Revision ID: 002
Revises: 001_add_subscription_table
Create Date: 2024-01-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '002'
down_revision = '001_add_subscription_table'
branch_labels = None
depends_on = None

def upgrade():
    # Create restaurant_chains table
    op.create_table(
        'restaurant_chains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_restaurant_chains_id', 'restaurant_chains', ['id'])

    # Create restaurant_outlets table
    op.create_table(
        'restaurant_outlets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chain_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('postal_code', sa.String(), nullable=False),
        sa.Column('country', sa.String(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['chain_id'], ['restaurant_chains.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_restaurant_outlets_id', 'restaurant_outlets', ['id'])
    op.create_index('ix_restaurant_outlets_chain_id', 'restaurant_outlets', ['chain_id'])

    # Drop old restaurants table
    op.drop_table('restaurants')

    # Update subscriptions table to reference chain_id instead of restaurant_id
    op.drop_constraint('subscriptions_user_id_fkey', 'subscriptions', type_='foreignkey')
    op.add_column('subscriptions', sa.Column('chain_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'subscriptions', 'restaurant_chains', ['chain_id'], ['id'])

def downgrade():
    # Revert subscriptions table changes
    op.drop_constraint(None, 'subscriptions', type_='foreignkey')
    op.drop_column('subscriptions', 'chain_id')
    op.create_foreign_key('subscriptions_user_id_fkey', 'subscriptions', 'users', ['user_id'], ['id'])

    # Drop new tables
    op.drop_index('ix_restaurant_outlets_chain_id', 'restaurant_outlets')
    op.drop_index('ix_restaurant_outlets_id', 'restaurant_outlets')
    op.drop_table('restaurant_outlets')
    op.drop_index('ix_restaurant_chains_id', 'restaurant_chains')
    op.drop_table('restaurant_chains')

    # Recreate original restaurants table
    op.create_table(
        'restaurants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )