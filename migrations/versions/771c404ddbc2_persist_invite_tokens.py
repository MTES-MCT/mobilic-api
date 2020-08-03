"""Persist invite tokens

Revision ID: 771c404ddbc2
Revises: de90912093ef
Create Date: 2020-08-03 10:53:39.412845

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "771c404ddbc2"
down_revision = "de90912093ef"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("either_user_id_or_invite_token_is_set", "employment")


def downgrade():
    op.create_check_constraint(
        "either_user_id_or_invite_token_is_set",
        "employment",
        "((user_id is not null)::bool != (invite_token is not null)::bool)",
    )
