"""Ajout du paramètre du nom de mission

Revision ID: fedbcc50bf6f
Revises: e0608dcf0866
Create Date: 2021-09-14 14:05:28.991594

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fedbcc50bf6f"
down_revision = "e0608dcf0866"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("company", sa.Column("require_mission_name", sa.Boolean()))
    op.execute("UPDATE public.company SET require_mission_name = true")
    op.alter_column("company", "require_mission_name", nullable=False)


# ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("company", "require_mission_name")
    # ### end Alembic commands ###
