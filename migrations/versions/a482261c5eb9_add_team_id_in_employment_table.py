"""Add team id in employment table

Revision ID: a482261c5eb9
Revises: 6e8011db8c1f
Create Date: 2023-02-16 10:58:07.664392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a482261c5eb9"
down_revision = "6e8011db8c1f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "employment", sa.Column("team_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_employment_team_id"), "employment", ["team_id"], unique=False
    )
    op.create_foreign_key(None, "employment", "team", ["team_id"], ["id"])


def downgrade():
    op.drop_constraint(None, "employment", type_="foreignkey")
    op.drop_index(op.f("ix_employment_team_id"), table_name="employment")
    op.drop_column("employment", "team_id")
