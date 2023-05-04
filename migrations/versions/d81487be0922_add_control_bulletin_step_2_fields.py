"""add control bulletin step 2 fields

Revision ID: d81487be0922
Revises: 961bdce1e519
Create Date: 2023-05-04 15:41:08.443681

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d81487be0922"
down_revision = "961bdce1e519"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "control_bulletin",
        sa.Column("articles_nature", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("company_address", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("company_name", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("license_copy_number", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("license_number", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("mission_address_begin", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("mission_address_end", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin", sa.Column("siren", sa.String(), nullable=True)
    )
    op.add_column(
        "control_bulletin",
        sa.Column("transport_type", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("vehicle_registration_country", sa.String(), nullable=True),
    )
    op.add_column(
        "control_bulletin",
        sa.Column("vehicle_registration_number", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("control_bulletin", "vehicle_registration_number")
    op.drop_column("control_bulletin", "vehicle_registration_country")
    op.drop_column("control_bulletin", "transport_type")
    op.drop_column("control_bulletin", "siren")
    op.drop_column("control_bulletin", "mission_address_end")
    op.drop_column("control_bulletin", "mission_address_begin")
    op.drop_column("control_bulletin", "license_number")
    op.drop_column("control_bulletin", "license_copy_number")
    op.drop_column("control_bulletin", "company_name")
    op.drop_column("control_bulletin", "company_address")
    op.drop_column("control_bulletin", "articles_nature")
