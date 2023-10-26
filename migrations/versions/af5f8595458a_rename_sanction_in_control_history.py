"""rename sanction in control history

Revision ID: af5f8595458a
Revises: 99c325b1b8c1
Create Date: 2023-10-26 09:26:06.840800

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "af5f8595458a"
down_revision = "99c325b1b8c1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE controller_control 
        SET observed_infractions = replace(observed_infractions::text, 'Sanction du Code du Travail', 'Non-respect du Code des transports')::jsonb
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE controller_control 
        SET observed_infractions = replace(observed_infractions::text, 'Non-respect du Code des transports', 'Sanction du Code du Travail')::jsonb
        """
    )
