"""refresh regulation check variables for moving transport type

Revision ID: 4ca13e06a9b5
Revises: e5d78113a5ac
Create Date: 2026-09-17 00:00:00.000000

"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import (
    update_regulation_check_variables,
)

# revision identifiers, used by Alembic.
revision = "4ca13e06a9b5"
down_revision = "e5d78113a5ac"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    update_regulation_check_variables(session)


def downgrade():
    pass
