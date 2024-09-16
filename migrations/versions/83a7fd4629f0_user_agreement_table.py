"""user agreement table

Revision ID: 83a7fd4629f0
Revises: 061ed7650780
Create Date: 2024-07-24 12:02:58.929733

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm.session import Session

from app.services.init_user_agreement import init_user_agreement

# revision identifiers, used by Alembic.
revision = "83a7fd4629f0"
down_revision = "061ed7650780"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_agreement",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cgu_version", sa.String(length=5), nullable=False),
        sa.Column(
            "answer_date",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "rejected",
                name="useragreementstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("transferred_data_date", sa.DateTime(), nullable=True),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "cgu_version", name="unique_user_cgu"),
    )
    op.create_index(
        op.f("ix_user_agreement_cgu_version"),
        "user_agreement",
        ["cgu_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_agreement_user_id"),
        "user_agreement",
        ["user_id"],
        unique=False,
    )

    # Insert one row for each user
    session = Session(bind=op.get_bind())
    init_user_agreement(session=session)


def downgrade():
    op.drop_index(
        op.f("ix_user_agreement_user_id"), table_name="user_agreement"
    )
    op.drop_index(
        op.f("ix_user_agreement_cgu_version"), table_name="user_agreement"
    )
    op.drop_table("user_agreement")
