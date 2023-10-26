"""Add key is_vehicle_immobilized defaut false to control_bulletin array in ControllerControl

Revision ID: dc0d42d537a6
Revises: 575d1a347d04
Create Date: 2023-09-29 14:35:25.704216

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "dc0d42d537a6"
down_revision = "575d1a347d04"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(
        "UPDATE controller_control SET control_bulletin = jsonb_set(control_bulletin, '{is_vehicle_immobilized}', 'false', true);"
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        "UPDATE controller_control SET control_bulletin = control_bulletin - 'is_vehicle_immobilized'"
    )
