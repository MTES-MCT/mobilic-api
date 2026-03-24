"""update no_lic regulation check label

Revision ID: f8a1b2c3d4e5
Revises: c3408857bc31
Create Date: 2026-03-16 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f8a1b2c3d4e5"
down_revision = "c3408857bc31"
branch_labels = None
depends_on = None

OLD_LABEL = "Absence de livret individuel de contrôle à bord"
NEW_LABEL = "Tenue non conforme du livret individuel de contrôle"


def upgrade():
    op.execute(
        sa.text(
            "UPDATE regulation_check SET label = :new_label WHERE type = 'noLic'"
        ).bindparams(new_label=NEW_LABEL)
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE regulation_check SET label = :old_label WHERE type = 'noLic'"
        ).bindparams(old_label=OLD_LABEL)
    )
