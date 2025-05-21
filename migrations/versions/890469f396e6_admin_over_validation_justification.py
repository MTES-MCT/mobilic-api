"""admin over validation justification

Revision ID: 890469f396e6
Revises: 4d83f466b18c
Create Date: 2025-05-21 11:10:01.551648

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "890469f396e6"
down_revision = "4d83f466b18c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mission_validation",
        sa.Column(
            "justification",
            sa.Enum(
                "personal",
                "professional",
                "time_off",
                name="overvalidationjustification",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "check_admin_justification_values",
        "mission_validation",
        "("
        "(NOT is_admin AND justification IS NULL) OR "
        "(is_admin AND (justification IS NULL OR justification IN ('personal', 'professional', 'time_off')))"
        ")",
    )


def downgrade():

    op.drop_column("mission_validation", "justification")
