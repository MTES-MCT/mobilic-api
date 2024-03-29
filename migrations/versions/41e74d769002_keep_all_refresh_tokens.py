"""Keep all refresh tokens

Revision ID: 41e74d769002
Revises: 7f8c48727acf
Create Date: 2021-03-15 11:23:24.321426

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "41e74d769002"
down_revision = "7f8c48727acf"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "refresh_token", sa.Column("consumed_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "refresh_token", sa.Column("deleted_at", sa.DateTime(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("refresh_token", "deleted_at")
    op.drop_column("refresh_token", "consumed_at")
    # ### end Alembic commands ###
