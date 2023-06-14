"""add extra column for controls

Revision ID: 0a99a53e565e
Revises: d81487be0922
Create Date: 2023-05-05 14:00:50.034102

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0a99a53e565e"
down_revision = "d81487be0922"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column(
            "extra",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("controller_control", "extra")
