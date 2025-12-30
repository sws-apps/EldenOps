"""Add github_token_encrypted to tenants table.

Revision ID: 001
Revises:
Create Date: 2024-12-16
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add github_token_encrypted column to tenants table."""
    op.add_column(
        'tenants',
        sa.Column('github_token_encrypted', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Remove github_token_encrypted column from tenants table."""
    op.drop_column('tenants', 'github_token_encrypted')
