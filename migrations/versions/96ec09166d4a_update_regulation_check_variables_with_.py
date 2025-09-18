"""Update regulation check variables with long break duration

Revision ID: 96ec09166d4a
Revises: eeed3eeec7de
Create Date: 2025-09-18 09:50:50.911461

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import (
    update_regulation_check_variables,
)


# revision identifiers, used by Alembic.
revision = "96ec09166d4a"
down_revision = "eeed3eeec7de"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    update_regulation_check_variables(session)


def downgrade():
    # we don't maintain a history of regulation checks
    pass
