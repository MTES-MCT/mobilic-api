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
            UPDATE regulatory_alert 
            SET extra=(extra#>>'{}')::jsonb 
            WHERE extra IS NOT NULL;
        """
    )


def downgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            UPDATE regulatory_alert
            SET extra = to_jsonb(quote_literal(extra::text))
            WHERE extra IS NOT NULL;
        """
    )
