"""migrate old control to new data model

Revision ID: 446e9197cf78
Revises: 4af1a795b88b
Create Date: 2023-06-07 15:34:16.837024

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "446e9197cf78"
down_revision = "4af1a795b88b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
            UPDATE controller_control c
            set user_first_name = (select first_name from "user" u where u.id = c.user_id),
                user_last_name = (select last_name from "user" u where u.id = c.user_id)
            where c.user_id is not null
        """
    )


def downgrade():
    op.execute(
        """
            UPDATE controller_control c
            set user_first_name = null,
                user_last_name = null
            where c.user_id is not null
        """
    )
