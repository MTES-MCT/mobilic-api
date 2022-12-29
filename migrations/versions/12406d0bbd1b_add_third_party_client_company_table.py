"""add third_party_client_company table

Revision ID: 12406d0bbd1b
Revises: 52434978c99e
Create Date: 2022-12-14 11:18:10.991713

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "12406d0bbd1b"
down_revision = "52434978c99e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "third_party_api_key",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("api_key", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth2_client.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_third_party_api_key_client_id"),
        "third_party_api_key",
        ["client_id"],
        unique=False,
    )

    op.create_table(
        "third_party_client_company",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "dismiss_context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
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
            ["company_id"],
            ["company.id"],
        ),
        sa.ForeignKeyConstraint(
            ["dismiss_author_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_third_party_client_company_client_id"),
        "third_party_client_company",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_third_party_client_company_company_id"),
        "third_party_client_company",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_third_party_client_company_dismiss_author_id"),
        "third_party_client_company",
        ["dismiss_author_id"],
        unique=False,
    )
    op.add_column(
        "oauth2_client",
        sa.Column("whitelist_ips", sa.ARRAY(sa.String()), nullable=True),
    )


def downgrade():
    op.drop_column("oauth2_client", "whitelist_ips")
    op.drop_index(
        op.f("ix_third_party_client_company_dismiss_author_id"),
        table_name="third_party_client_company",
    )
    op.drop_index(
        op.f("ix_third_party_client_company_company_id"),
        table_name="third_party_client_company",
    )
    op.drop_index(
        op.f("ix_third_party_client_company_client_id"),
        table_name="third_party_client_company",
    )
    op.drop_table("third_party_client_company")
    op.drop_index(
        op.f("ix_third_party_api_key_client_id"),
        table_name="third_party_api_key",
    )
    op.drop_table("third_party_api_key")
    # ### end Alembic commands ###
