"""third_party_client_employment.invitation_token can be null

Revision ID: 80dfc91bbd27
Revises: b5afcd504879
Create Date: 2022-12-28 16:28:32.007804

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "80dfc91bbd27"
down_revision = "b5afcd504879"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "third_party_client_employment", "invitation_token", nullable=True
    )


def downgrade():
    op.alter_column(
        "third_party_client_employment", "invitation_token", nullable=False
    )
