"""Add company admin flag

Revision ID: 92c1622e406a
Revises: 1f0d730d08b8
Create Date: 2020-02-10 20:32:54.201283

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "92c1622e406a"
down_revision = "1f0d730d08b8"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "user", sa.Column("is_company_admin", sa.Boolean(), nullable=True)
    )
    op.execute("UPDATE public.user SET is_company_admin = true")
    op.alter_column("user", "is_company_admin", nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("user", "is_company_admin")
    # ### end Alembic commands ###
