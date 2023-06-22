"""add note to control

Revision ID: d342aeb2a88f
Revises: 446e9197cf78
Create Date: 2023-06-21 17:25:05.906058

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d342aeb2a88f"
down_revision = "446e9197cf78"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control", sa.Column("note", sa.TEXT(), nullable=True)
    )


def downgrade():
    op.drop_column("controller_control", "note")
