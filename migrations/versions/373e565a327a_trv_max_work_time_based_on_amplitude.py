"""update_trv_descriptions_max_work_time_based_on_amplitude

Revision ID: 373e565a327a
Revises: 7e8f71c49544
Create Date: 2025-02-06 09:41:41.254918

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import get_regulation_checks


# revision identifiers, used by Alembic.
revision = "373e565a327a"
down_revision = "7e8f71c49544"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    regulation_check_data = get_regulation_checks()
    for r in regulation_check_data:
        session.execute(
            sa.text(
                "UPDATE regulation_check SET variables = :variables WHERE type = :type;"
            ),
            dict(
                variables=json.dumps(r.variables),
                type=r.type,
            ),
        )


def downgrade():
    pass
