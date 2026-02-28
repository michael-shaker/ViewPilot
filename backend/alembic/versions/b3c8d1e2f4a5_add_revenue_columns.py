"""add revenue columns to video_analytics

Revision ID: b3c8d1e2f4a5
Revises: 40ffc9b22f66
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c8d1e2f4a5'
down_revision = '40ffc9b22f66'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('video_analytics', sa.Column('estimated_revenue', sa.Float(), nullable=True))
    op.add_column('video_analytics', sa.Column('estimated_ad_revenue', sa.Float(), nullable=True))
    op.add_column('video_analytics', sa.Column('rpm', sa.Float(), nullable=True))
    op.add_column('video_analytics', sa.Column('cpm', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('video_analytics', 'cpm')
    op.drop_column('video_analytics', 'rpm')
    op.drop_column('video_analytics', 'estimated_ad_revenue')
    op.drop_column('video_analytics', 'estimated_revenue')
