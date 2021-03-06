"""Update mission validation

Revision ID: f2128b73734b
Revises: f62872528474
Create Date: 2020-11-12 14:48:19.745155

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2128b73734b"
down_revision = "f62872528474"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mission_validation",
        sa.Column("is_admin", sa.Boolean(), nullable=True),
    )
    op.execute("UPDATE mission_validation SET is_admin = false")
    op.alter_column("mission_validation", "is_admin", nullable=False)
    op.add_column(
        "mission_validation", sa.Column("user_id", sa.Integer(), nullable=True)
    )
    op.execute("UPDATE mission_validation SET user_id = submitter_id")
    op.create_check_constraint(
        "non_admin_can_only_validate_for_self",
        "mission_validation",
        "(is_admin OR (user_id = submitter_id))",
    )
    op.create_index(
        op.f("ix_mission_validation_user_id"),
        "mission_validation",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        None, "mission_validation", "user", ["user_id"], ["id"]
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_mission_validation_user_id"), table_name="mission_validation"
    )
    op.drop_column("mission_validation", "user_id")
    op.drop_column("mission_validation", "is_admin")
    # ### end Alembic commands ###
