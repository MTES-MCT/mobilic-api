"""clean_scenario_testing

Revision ID: b93eeb578bdd
Revises: f690b917edae
Create Date: 2023-08-21 14:07:40.391195

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b93eeb578bdd"
down_revision = "f690b917edae"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM scenario_testing")
    op.execute("REINDEX TABLE scenario_testing")


def downgrade():
    # do nothing
    pass
