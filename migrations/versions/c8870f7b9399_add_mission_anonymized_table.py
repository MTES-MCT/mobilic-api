"""Add mission_anonymized table

Revision ID: c8870f7b9399
Revises: bd643a8d5269
Create Date: 2024-11-07 12:34:16.339041

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8870f7b9399"
down_revision = "bd643a8d5269"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "mission_anonymized",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("submitter_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("creation_time", sa.DateTime(), nullable=True),
        sa.Column("reception_time", sa.DateTime(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("mission_anonymized")
    # ### end Alembic commands ###
