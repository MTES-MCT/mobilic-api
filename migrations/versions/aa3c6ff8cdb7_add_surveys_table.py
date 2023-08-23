"""add surveys table

Revision ID: aa3c6ff8cdb7
Revises: f690b917edae
Create Date: 2023-08-22 17:15:41.202368

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aa3c6ff8cdb7"
down_revision = "f690b917edae"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_survey_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("survey_id", sa.String(length=255), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "DISPLAY",
                "CLOSE",
                "SUBMIT",
                name="surveyaction",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_survey_actions_survey_id"),
        "user_survey_actions",
        ["survey_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_survey_actions_user_id"),
        "user_survey_actions",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_user_survey_actions_user_id"),
        table_name="user_survey_actions",
    )
    op.drop_index(
        op.f("ix_user_survey_actions_survey_id"),
        table_name="user_survey_actions",
    )
    op.drop_table("user_survey_actions")
