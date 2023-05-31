"""refactor control bulletin model

Revision ID: 2b39e364997a
Revises: 8306696143fd
Create Date: 2023-05-30 23:25:03.158728

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2b39e364997a"
down_revision = "8306696143fd"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(
        "ix_control_bulletin_control_id", table_name="control_bulletin"
    )
    op.drop_table("control_bulletin")
    op.add_column(
        "controller_control",
        sa.Column(
            "control_bulletin",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "controller_control",
        sa.Column(
            "control_bulletin_creation_time", sa.DateTime, nullable=True
        ),
    )
    op.add_column(
        "controller_control",
        sa.Column("user_first_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "controller_control",
        sa.Column("user_last_name", sa.String(length=255), nullable=True),
    )
    op.drop_column("controller_control", "extra")
    # ### end Alembic commands ###


def downgrade():
    op.add_column(
        "controller_control",
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_column("controller_control", "user_last_name")
    op.drop_column("controller_control", "user_first_name")
    op.drop_column("controller_control", "control_bulletin_creation_time")
    op.drop_column("controller_control", "control_bulletin")
    op.create_table(
        "control_bulletin",
        sa.Column(
            "control_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "creation_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "user_first_name",
            sa.VARCHAR(length=255),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "user_last_name",
            sa.VARCHAR(length=255),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "lic_paper_presented",
            sa.BOOLEAN(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "user_birth_date", sa.DATE(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "user_nationality",
            sa.VARCHAR(length=255),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "articles_nature", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "company_address", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "company_name", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "license_copy_number",
            sa.VARCHAR(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "license_number", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "mission_address_begin",
            sa.VARCHAR(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "mission_address_end",
            sa.VARCHAR(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("siren", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column(
            "transport_type", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "vehicle_registration_country",
            sa.VARCHAR(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "vehicle_registration_number",
            sa.VARCHAR(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "observation", sa.TEXT(), autoincrement=False, nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["controller_control.id"],
            name="control_bulletin_control_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="control_bulletin_pkey"),
    )
    op.create_index(
        "ix_control_bulletin_control_id",
        "control_bulletin",
        ["control_id"],
        unique=True,
    )
    # ### end Alembic commands ###
