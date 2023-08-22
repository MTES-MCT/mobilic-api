"""no lic nb controlled days

Revision ID: f690b917edae
Revises: 5c98ea186ad7
Create Date: 2023-08-21 16:34:01.990000

"""
from alembic import op
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision = "f690b917edae"
down_revision = "5c98ea186ad7"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            UPDATE controller_control
            SET nb_controlled_days = 7
            WHERE control_type = 'sans_lic'
        """
    )


def downgrade():
    pass
