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
            UPDATE controller_control 
            SET control_bulletin=(control_bulletin#>>'{}')::jsonb 
            WHERE control_bulletin IS NOT NULL;
        """
    )


def downgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            UPDATE controller_control
            SET control_bulletin = to_jsonb(quote_literal(control_bulletin::text))
            WHERE control_bulletin IS NOT NULL;
        """
    )
