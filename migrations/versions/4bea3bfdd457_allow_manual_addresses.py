"""Allow manual addresses

Revision ID: 4bea3bfdd457
Revises: 0b6d2cef18e8
Create Date: 2021-02-10 12:09:33.723169

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4bea3bfdd457"
down_revision = "0b6d2cef18e8"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("address", sa.Column("manual", sa.Boolean(), nullable=True))
    op.execute("UPDATE address SET manual = false")
    op.alter_column("address", "manual", nullable=False)
    op.alter_column(
        "address", "city", existing_type=sa.VARCHAR(length=255), nullable=True
    )
    op.alter_column(
        "address",
        "coords",
        existing_type=postgresql.ARRAY(sa.NUMERIC()),
        nullable=True,
    )
    op.alter_column(
        "address",
        "geo_api_id",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )
    op.alter_column(
        "address",
        "postal_code",
        existing_type=sa.VARCHAR(length=20),
        nullable=True,
    )
    op.alter_column(
        "address", "type", existing_type=sa.VARCHAR(length=20), nullable=True
    )
    op.alter_column("address", "geo_api_raw_data", nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "address", "type", existing_type=sa.VARCHAR(length=20), nullable=False
    )
    op.alter_column(
        "address",
        "postal_code",
        existing_type=sa.VARCHAR(length=20),
        nullable=False,
    )
    op.alter_column(
        "address",
        "geo_api_id",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )
    op.alter_column(
        "address",
        "coords",
        existing_type=postgresql.ARRAY(sa.NUMERIC()),
        nullable=False,
    )
    op.alter_column(
        "address", "city", existing_type=sa.VARCHAR(length=255), nullable=False
    )
    op.drop_column("address", "manual")
    op.alter_column("address", "geo_api_raw_data", nullable=False)

    # ### end Alembic commands ###
