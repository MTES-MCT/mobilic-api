"""merge sent_to_driver and anon_controller_control user_id heads

Revision ID: 39f51c6db221
Revises: e6015df7d17e, 68f7e34e43f8
Create Date: 2026-10-01 00:00:00.000000

"""

revision = "39f51c6db221"
down_revision = ("e6015df7d17e", "68f7e34e43f8")
branch_labels = None
depends_on = None


def upgrade():
    # no-op: pure merge node in the alembic DAG, both parents already applied
    pass


def downgrade():
    # no-op: cannot un-merge, downgrade one parent at a time instead
    pass
