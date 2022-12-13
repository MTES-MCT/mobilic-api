"""add api key management

Revision ID: 87b77deb8c73
Revises: 52434978c99e
Create Date: 2022-12-13 08:45:29.011279

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "87b77deb8c73"
down_revision = "52434978c99e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oauth2_api_key",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("api_key", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth2_client.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oauth2_api_key_client_id"),
        "oauth2_api_key",
        ["client_id"],
        unique=False,
    )
    op.add_column(
        "oauth2_client",
        sa.Column("whitelist_ips", sa.ARRAY(sa.String()), nullable=True),
    )


def downgrade():
    op.drop_column("oauth2_client", "whitelist_ips")
    op.drop_index(
        op.f("ix_oauth2_api_key_client_id"), table_name="oauth2_api_key"
    )
    op.drop_table("oauth2_api_key")
