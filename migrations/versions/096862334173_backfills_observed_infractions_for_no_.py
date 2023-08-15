"""backfills observed_infractions for no lic controls

Revision ID: 096862334173
Revises: 88948031a878
Create Date: 2023-08-15 12:31:18.349021

"""
from alembic import op
from sqlalchemy.orm import Session

from app.domain.controller import get_no_lic_observed_infractions
from app.models.controller_control import ControllerControl

# revision identifiers, used by Alembic.
revision = "096862334173"
down_revision = "88948031a878"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    no_lic_controls = conn.execute(
        """
        SELECT id
        FROM controller_control
        WHERE control_type = 'sans_lic'
        """
    )
    session = Session(bind=conn)

    for record in no_lic_controls:
        control = (
            session.query(ControllerControl).filter_by(id=record.id).first()
        )
        observed_infractions = get_no_lic_observed_infractions(
            control.creation_time.date()
        )
        control.observed_infractions = observed_infractions
    session.commit()
    session.close()


def downgrade():
    pass
