"""add subscription table

Revision ID: 001
Revises: 
Create Date: 2024-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create SubscriptionTier enum type
    subscription_tier = postgresql.ENUM('free', 'basic', 'premium', name='subscriptiontier')
    subscription_tier.create(op.get_bind())

    # Create SubscriptionStatus enum type
    subscription_status = postgresql.ENUM('active', 'expired', 'cancelled', name='subscriptionstatus')
    subscription_status.create(op.get_bind())

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tier', sa.Enum('free', 'basic', 'premium', name='subscriptiontier'), nullable=False),
        sa.Column('status', sa.Enum('active', 'expired', 'cancelled', name='subscriptionstatus'), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_subscriptions_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
    op.execute('DROP TYPE subscriptiontier')
    op.execute('DROP TYPE subscriptionstatus')