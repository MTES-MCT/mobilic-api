"""update_trv_descriptions_max_work_time_based_on_amplitude

Revision ID: 373e565a327a
Revises: 7e8f71c49544
Create Date: 2025-02-06 09:41:41.254918

"""
import json

from alembic import op
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import (
    update_regulation_check_variables,
)

# revision identifiers, used by Alembic.
revision = "373e565a327a"
down_revision = "7e8f71c49544"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    update_regulation_check_variables(session)


def downgrade():
    # we don't maintain a history of regulation checks
    pass
