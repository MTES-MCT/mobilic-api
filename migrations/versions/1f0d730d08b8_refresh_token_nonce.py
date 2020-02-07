"""refresh token nonce

Revision ID: 1f0d730d08b8
Revises: 74b82d635596
Create Date: 2020-02-07 13:06:48.791585

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f0d730d08b8"
down_revision = "74b82d635596"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column("refresh_token_nonce", sa.String(length=255), nullable=True),
    )
    op.drop_column("user", "token")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "user",
        sa.Column(
            "token", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
    )
    op.drop_column("user", "refresh_token_nonce")
    # ### end Alembic commands ###
