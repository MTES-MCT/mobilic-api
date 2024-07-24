"""update regulation check descriptions

Revision ID: 99c325b1b8c1
Revises: 30cee055a36e
Create Date: 2023-10-19 18:02:18.886278

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm.session import Session
from app.services.get_regulation_checks import get_regulation_checks


# revision identifiers, used by Alembic.
revision = "99c325b1b8c1"
down_revision = "30cee055a36e"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
