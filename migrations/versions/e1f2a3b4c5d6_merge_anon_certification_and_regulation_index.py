"""merge anon_company_certification refactor and regulation_computation index heads

Revision ID: e1f2a3b4c5d6
Revises: a7c1f2b9d4e6, c8f1a2b3d4e5
Create Date: 2026-08-06 20:10:00.000000

"""

revision = "e1f2a3b4c5d6"
down_revision = ("a7c1f2b9d4e6", "c8f1a2b3d4e5")
branch_labels = None
depends_on = None


def upgrade():
    # no-op: pure merge node in the alembic DAG, both parents already applied
    pass


def downgrade():
    # no-op: cannot un-merge, downgrade one parent at a time instead
    pass
