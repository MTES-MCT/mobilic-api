"""Change base validation status enum

Revision ID: 475ecb05cb24
Revises: e7e59e36d8f6
Create Date: 2020-02-10 23:59:47.794107

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "475ecb05cb24"
down_revision = "e7e59e36d8f6"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("eventbasevalidationstatus", "expenditure")
    op.alter_column(
        "expenditure",
        "validation_status",
        type_=sa.Enum(
            "unauthorized_submitter",
            "validated",
            "pending",
            "rejected",
            name="eventbasevalidationstatus",
            native_enum=False,
        ),
        nullable=False,
    )
    op.alter_column("activity", "type", nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("eventbasevalidationstatus", "expenditure")
    op.alter_column(
        "expenditure",
        "validation_status",
        type_=sa.Enum(
            "validated",
            "pending",
            "rejected",
            name="eventbasevalidationstatus",
            native_enum=False,
        ),
        nullable=True,
    )
    op.alter_column("activity", "type", nullable=True)
    # ### end Alembic commands ###
