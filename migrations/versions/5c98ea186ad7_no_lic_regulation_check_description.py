"""no lic regulation check description

Revision ID: 5c98ea186ad7
Revises: 096862334173
Create Date: 2023-08-21 10:49:31.270894

"""
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = "5c98ea186ad7"
down_revision = "096862334173"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            UPDATE regulation_check
            SET description = 'Défaut de documents nécessaires au décompte de la durée du travail (L. 3121-67 du Code du travail et R. 3312-58 du Code des transports + arrêté du 20 juillet 1998)'
            WHERE type = 'noLic'
        """
    )


def downgrade():
    pass
