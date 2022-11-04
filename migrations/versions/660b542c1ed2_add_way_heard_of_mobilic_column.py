"""Add way heard of Mobilic column

Revision ID: 660b542c1ed2
Revises: 6ff0c4124a0c
Create Date: 2022-11-04 14:45:24.274785

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "660b542c1ed2"
down_revision = "6ff0c4124a0c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "way_heard_of_mobilic", sa.String(length=255), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_user_way_heard_of_mobilic"),
        "user",
        ["way_heard_of_mobilic"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_user_way_heard_of_mobilic"), table_name="user")
    op.drop_column("user", "way_heard_of_mobilic")
