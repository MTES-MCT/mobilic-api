"""backfills observed_infractions for mobilic controls

Revision ID: 575d1a347d04
Revises: 27655467d715
Create Date: 2023-09-05 10:33:30.873552

"""
from alembic import op
from sqlalchemy.orm import Session

from app.models.controller_control import ControllerControl

# revision identifiers, used by Alembic.
revision = "575d1a347d04"
down_revision = "27655467d715"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    mobilic_controls = conn.execute(
        """
        SELECT id
        FROM controller_control
        WHERE control_type = 'mobilic'
        AND observed_infractions IS NULL
        """
    )
    session = Session(bind=conn)

    for record in mobilic_controls:
        control = (
            session.query(ControllerControl).filter_by(id=record.id).first()
        )
        control.report_infractions()
        session.commit()

    session.close()


def downgrade():
    pass
