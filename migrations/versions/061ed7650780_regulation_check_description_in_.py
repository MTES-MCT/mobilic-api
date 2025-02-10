"""regulation check description in variables

Revision ID: 061ed7650780
Revises: 02b1e89f1165
Create Date: 2024-07-16 15:23:52.773817

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import (
    update_regulation_check_variables,
)

# revision identifiers, used by Alembic.
revision = "061ed7650780"
down_revision = "02b1e89f1165"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    update_regulation_check_variables(session)
    op.drop_column("regulation_check", "description")


def downgrade():
    op.add_column(
        "regulation_check", sa.Column("description", sa.TEXT(), nullable=True)
    )
