"""employment: share email option

Revision ID: 2179a955a24d
Revises: 99c325b1b8c1
Create Date: 2023-10-25 11:07:43.890264

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "2179a955a24d"
down_revision = "99c325b1b8c1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "employment", sa.Column("hide_email", sa.Boolean(), nullable=True)
    )
    session = Session(bind=op.get_bind())
    session.execute("UPDATE employment SET hide_email = FALSE")


def downgrade():
    op.drop_column("employment", "hide_email")
