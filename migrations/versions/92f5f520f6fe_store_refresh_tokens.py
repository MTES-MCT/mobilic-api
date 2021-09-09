"""store refresh tokens

Revision ID: 92f5f520f6fe
Revises: 2e6b59be046b
Create Date: 2020-08-18 15:36:53.852813

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "92f5f520f6fe"
down_revision = "2e6b59be046b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "refresh_token",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_refresh_token_user_id"),
        "refresh_token",
        ["user_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_refresh_token_user_id"), table_name="refresh_token")
    op.drop_table("refresh_token")
    # ### end Alembic commands ###
