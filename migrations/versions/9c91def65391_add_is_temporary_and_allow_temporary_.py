"""add is_temporary and allow_temporary_employees

Revision ID: 9c91def65391
Revises: b1f4a9c7e2d8
Create Date: 2026-11-08 14:44:38.233402

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c91def65391"
down_revision = "b1f4a9c7e2d8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "employment",
        sa.Column(
            "is_temporary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "company",
        sa.Column(
            "allow_temporary_employees",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("employment", "is_temporary")
    op.drop_column("company", "allow_temporary_employees")
