"""merge heads 39f51c6db221 and c3d8e1f4a2b7

Revision ID: a7f2c9e4b831
Revises: 39f51c6db221, c3d8e1f4a2b7
Create Date: 2026-10-12 00:00:00.000000

"""

revision = "a7f2c9e4b831"
down_revision = ("39f51c6db221", "c3d8e1f4a2b7")
branch_labels = None
depends_on = None


def upgrade():
    # no-op: pure merge node in the alembic DAG, both parents already applied
    pass


def downgrade():
    # no-op: cannot un-merge, downgrade one parent at a time instead
    pass
