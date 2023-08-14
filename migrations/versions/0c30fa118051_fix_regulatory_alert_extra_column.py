"""fix regulatory alert extra column

Revision ID: 0c30fa118051
Revises: f628bed57b6c
Create Date: 2023-08-11 17:43:39.295011

"""
from alembic import op
from sqlalchemy.orm.session import Session

# revision identifiers, used by Alembic.
revision = "0c30fa118051"
down_revision = "f628bed57b6c"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            update regulatory_alert
            set extra = substring(replace(extra::text, '\\"', '"'), 2, length(replace(extra::text, '\\"', '"')) - 2)::jsonb
            where extra is not null;
        """
    )


def downgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            update regulatory_alert
            set extra = to_json(extra::text)
            where extra is not null;
        """
    )
