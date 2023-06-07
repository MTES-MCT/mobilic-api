"""add bdc's download time

Revision ID: 4af1a795b88b
Revises: 2b39e364997a
Create Date: 2023-06-06 11:48:47.214564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4af1a795b88b"
down_revision = "2b39e364997a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "controller_control",
        sa.Column(
            "control_bulletin_first_download_time", sa.DateTime, nullable=True
        ),
    )


def downgrade():
    op.drop_column(
        "controller_control", "control_bulletin_first_download_time"
    )
