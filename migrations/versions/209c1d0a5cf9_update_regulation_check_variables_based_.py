"""update regulation check variables based on businesses

Revision ID: 209c1d0a5cf9
Revises: aa1096a64d0f
Create Date: 2024-07-09 11:25:29.813283

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services.get_regulation_checks import get_regulation_checks

# revision identifiers, used by Alembic.
revision = "209c1d0a5cf9"
down_revision = "aa1096a64d0f"
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
