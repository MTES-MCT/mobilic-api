"""fix NATINF for maximumWorkedDaysInWeek check

Revision ID: ecc1e9f03ce8
Revises: b00eb3b480ac
Create Date: 2023-08-14 17:03:53.534078

"""
from alembic import op
from sqlalchemy.orm.session import Session

# revision identifiers, used by Alembic.
revision = "ecc1e9f03ce8"
down_revision = "b00eb3b480ac"
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            update regulatory_alert
            set extra = '{"sanction_code": "NATINF 13152"}' || extra
            where regulation_check_id = (select id from regulation_check where type = 'maximumWorkedDaysInWeek')
            and extra ->>'sanction_code' is null;
        """
    )


def downgrade():
    session = Session(bind=op.get_bind())
    session.execute(
        """
            update regulatory_alert
            set extra = extra - 'sanction_code'
            where regulation_check_id = (select id from regulation_check where type = 'maximumWorkedDaysInWeek')
            and extra ->>'rest_duration_s' is null;
        """
    )
