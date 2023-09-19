"""fix control bulletin column

Revision ID: b00eb3b480ac
Revises: 0c30fa118051
Create Date: 2023-08-14 11:54:36.304057

"""
from alembic import op
from sqlalchemy.orm.session import Session

# revision identifiers, used by Alembic.
revision = "b00eb3b480ac"
down_revision = "0c30fa118051"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            update controller_control
            set control_bulletin = substring(replace(control_bulletin::text, '\\"', '"'), 2, length(replace(control_bulletin::text, '\\"', '"')) - 2)::jsonb
            where control_bulletin is not null;
        """
    )


def downgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            update controller_control
            set control_bulletin = to_json(control_bulletin::text)
            where control_bulletin is not null;
        """
    )
