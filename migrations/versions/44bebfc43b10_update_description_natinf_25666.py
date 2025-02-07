"""update description natinf 25666

Revision ID: 44bebfc43b10
Revises: 373e565a327a
Create Date: 2025-02-07 10:39:30.719398

"""
from alembic import op
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import (
    update_regulation_check_variables,
)

# revision identifiers, used by Alembic.
revision = "44bebfc43b10"
down_revision = "373e565a327a"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    update_regulation_check_variables(session)


def downgrade():
    pass
