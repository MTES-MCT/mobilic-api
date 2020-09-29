"""Update employment constraint

Revision ID: eb2980d5acfe
Revises: 1fe02d4c1330
Create Date: 2020-09-29 12:04:31.643877

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "eb2980d5acfe"
down_revision = "1fe02d4c1330"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "only_one_current_primary_employment_per_user", "employment"
    )
    op.execute(
        """
        ALTER TABLE employment ADD CONSTRAINT only_one_current_primary_employment_per_user
        EXCLUDE USING GIST (
            user_id WITH =,
            daterange(start_date, CASE WHEN end_date is not null THEN end_date ELSE '2100-01-01' END, '[]') WITH &&
        )
        WHERE (is_primary AND validation_status != 'rejected' AND dismissed_at IS NULL)
        """
    )

    op.drop_constraint(
        "no_simultaneous_employments_for_the_same_company", "employment"
    )
    op.execute(
        """
        ALTER TABLE employment ADD CONSTRAINT no_simultaneous_employments_for_the_same_company
        EXCLUDE USING GIST (
            user_id WITH =,
            company_id WITH =,
            daterange(start_date, CASE WHEN end_date is not null THEN end_date ELSE '2100-01-01' END, '[]') WITH &&
        )
        WHERE (validation_status != 'rejected' AND dismissed_at IS NULL)
        """
    )


def downgrade():
    op.drop_constraint(
        "only_one_current_primary_employment_per_user", "employment"
    )
    op.execute(
        """
        ALTER TABLE employment ADD CONSTRAINT only_one_current_primary_employment_per_user
        EXCLUDE USING GIST (
            user_id WITH =,
            daterange(start_date, CASE WHEN end_date is not null THEN end_date ELSE '2100-01-01' END, '[]') WITH &&
        )
        WHERE (is_primary AND validation_status != 'rejected')
        """
    )

    op.drop_constraint(
        "no_simultaneous_employments_for_the_same_company", "employment"
    )
    op.execute(
        """
        ALTER TABLE employment ADD CONSTRAINT no_simultaneous_employments_for_the_same_company
        EXCLUDE USING GIST (
            user_id WITH =,
            company_id WITH =,
            daterange(start_date, CASE WHEN end_date is not null THEN end_date ELSE '2100-01-01' END, '[]') WITH &&
        )
        WHERE (validation_status != 'rejected')
        """
    )
