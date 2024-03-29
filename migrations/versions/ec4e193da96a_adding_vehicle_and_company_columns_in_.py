"""Adding vehicle and company columns in ControllerControl

Revision ID: ec4e193da96a
Revises: f08bc938b26b
Create Date: 2022-08-19 09:45:57.311471

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ec4e193da96a"
down_revision = "f08bc938b26b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "controller_control",
        sa.Column("company_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "controller_control",
        sa.Column("vehicle_registration_number", sa.TEXT(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("controller_control", "vehicle_registration_number")
    op.drop_column("controller_control", "company_name")
    # ### end Alembic commands ###
