"""update regulation check variables based on businesses

Revision ID: 209c1d0a5cf9
Revises: aa1096a64d0f
Create Date: 2024-07-09 11:25:29.813283

"""
from alembic import op
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import (
    update_regulation_check_variables,
)

# revision identifiers, used by Alembic.
revision = "209c1d0a5cf9"
down_revision = "aa1096a64d0f"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    update_regulation_check_variables(session)


def downgrade():
    pass
