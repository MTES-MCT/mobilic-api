"""Remove no_successive_types_constraint

Revision ID: f62872528474
Revises: a1b289f48774
Create Date: 2020-10-28 22:05:16.277564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f62872528474"
down_revision = "a1b289f48774"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("no_sucessive_activities_with_same_type", "activity")


def downgrade():
    pass
