"""Add event fields to Schedule table

Revision ID: add_event_fields
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_event_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to Schedule table
    op.add_column('schedule', sa.Column('is_event', sa.Boolean(), nullable=True, default=False))
    op.add_column('schedule', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('schedule', sa.Column('event_type', sa.String(50), nullable=True))


def downgrade():
    # Remove the columns
    op.drop_column('schedule', 'event_type')
    op.drop_column('schedule', 'description')
    op.drop_column('schedule', 'is_event')
