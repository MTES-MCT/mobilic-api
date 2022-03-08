"""Ajout des temps de liaison en tant que type d'activite

Revision ID: bc7abe3eb83c
Revises: 915e0942f14f
Create Date: 2022-02-16 14:13:58.659900

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "bc7abe3eb83c"
down_revision = "915e0942f14f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "company", sa.Column("allow_transfers", sa.Boolean(), nullable=True)
    )
    op.execute("UPDATE company SET allow_transfers = false")
    op.alter_column("company", "allow_transfers", nullable=False)

    # add 'transfer' in activity type enum
    op.drop_constraint("activitytypes", "activity")
    op.alter_column(
        "activity",
        "type",
        type_=sa.Enum(
            "drive",
            "support",
            "work",
            "transfer",
            name="activitytypes",
            native_enum=False,
        ),
        nullable=False,
    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("company", "allow_transfers")
    # ### end Alembic commands ###
