"""activity last submitter id fkey deferrable

Revision ID: 9e2eb44e464d
Revises: ec4e193da96a
Create Date: 2022-09-08 16:48:24.782393

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9e2eb44e464d"
down_revision = "ec4e193da96a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "activity_last_submitter_id_fkey", "activity", type_="foreignkey"
    )
    op.create_foreign_key(
        None,
        "activity",
        "user",
        ["last_submitter_id"],
        ["id"],
        deferrable=True,
        initially="deferred",
    )


def downgrade():
    op.drop_constraint(
        "activity_last_submitter_id_fkey", "activity", type_="foreignkey"
    )
    op.create_foreign_key(
        "activity_last_submitter_id_fkey",
        "activity",
        "user",
        ["last_submitter_id"],
        ["id"],
    )
