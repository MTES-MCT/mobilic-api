"""remove regulation rule not null constraint

Revision ID: bd0cdf9f16bd
Revises: 06188fcde16b
Create Date: 2024-11-21 13:08:06.436526

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bd0cdf9f16bd"
down_revision = "06188fcde16b"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("regulation_check", "regulation_rule", nullable=True)


def downgrade():
    op.alter_column("regulation_check", "regulation_rule", nullable=False)
