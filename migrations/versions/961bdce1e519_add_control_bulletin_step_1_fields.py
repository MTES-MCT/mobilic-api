"""add control bulletin step 1 fields

Revision ID: 961bdce1e519
Revises: b7270c163b14
Create Date: 2023-05-02 16:37:46.409722

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "961bdce1e519"
down_revision = "b7270c163b14"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "control_bulletin",
        sa.Column("lic_paper_presented", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("user_birth_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("user_nationality", sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column("control_bulletin", "user_nationality")
    op.drop_column("control_bulletin", "user_birth_date")
    op.drop_column("control_bulletin", "lic_paper_presented")
