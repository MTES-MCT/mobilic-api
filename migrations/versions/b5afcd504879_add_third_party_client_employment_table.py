"""add third_party_client_employment table

Revision ID: b5afcd504879
Revises: 12406d0bbd1b
Create Date: 2022-12-25 20:07:14.726866

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b5afcd504879"
down_revision = "12406d0bbd1b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "third_party_client_employment",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "dismiss_context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("employment_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.String(length=255), nullable=True),
        sa.Column("invitation_token", sa.String(length=255), nullable=False),
        sa.Column(
            "invitation_token_creation_time", sa.DateTime(), nullable=False
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dismiss_author_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "((dismissed_at is not null)::bool = (dismiss_author_id is not null)::bool)",
            name="non_nullable_dismiss_info",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth2_client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["dismiss_author_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["employment_id"],
            ["employment.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_third_party_client_employment_client_id"),
        "third_party_client_employment",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_third_party_client_employment_dismiss_author_id"),
        "third_party_client_employment",
        ["dismiss_author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_third_party_client_employment_employment_id"),
        "third_party_client_employment",
        ["employment_id"],
        unique=False,
    )
    op.add_column(
        "employment",
        sa.Column("external_id", sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column("employment", "external_id")
    op.drop_index(
        op.f("ix_third_party_client_employment_employment_id"),
        table_name="third_party_client_employment",
    )
    op.drop_index(
        op.f("ix_third_party_client_employment_dismiss_author_id"),
        table_name="third_party_client_employment",
    )
    op.drop_index(
        op.f("ix_third_party_client_employment_client_id"),
        table_name="third_party_client_employment",
    )
    op.drop_table("third_party_client_employment")
