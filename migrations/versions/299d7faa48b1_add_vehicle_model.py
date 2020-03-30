"""Add vehicle model

Revision ID: 299d7faa48b1
Revises: adca0746dd7d
Create Date: 2020-03-30 14:15:53.587754

"""
from collections import defaultdict
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm.session import Session


# revision identifiers, used by Alembic.
revision = "299d7faa48b1"
down_revision = "adca0746dd7d"
branch_labels = None
depends_on = None


def _migrate_vehicles():
    session = Session(bind=op.get_bind())
    vehicles_to_create = defaultdict(dict)
    vehicle_bookings = session.execute(
        """
        SELECT registration_number, event_time, submitter_id, company_id
        FROM vehicle_booking
        """
    )

    for vehicle_booking in sorted(vehicle_bookings, key=lambda vb: vb[1]):
        company_id = vehicle_booking[3]
        if vehicle_booking[0] not in vehicles_to_create[company_id]:
            vehicles_to_create[company_id][
                vehicle_booking[0]
            ] = vehicle_booking[2]

    for company_id, vehicles in vehicles_to_create.items():
        for registration_number, submitter_id in vehicles.items():
            session.execute(
                """
                INSERT INTO vehicle(
                    creation_time,
                    registration_number,
                    alias,
                    submitter_id,
                    company_id
                )
                VALUES(
                    NOW(),
                    :registration_number,
                    NULL,
                    :submitter_id,
                    :company_id
                )
                """,
                dict(
                    submitter_id=submitter_id,
                    company_id=company_id,
                    registration_number=registration_number,
                ),
            )
    session.flush()

    session.execute(
        """
        UPDATE vehicle_booking vb SET vehicle_id = v.id
        FROM vehicle v
        WHERE v.company_id = vb.company_id AND v.registration_number = vb.registration_number
        """
    )
    session.flush()


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "vehicle",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("registration_number", sa.TEXT(), nullable=False),
        sa.Column("alias", sa.TEXT(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"],),
        sa.ForeignKeyConstraint(["submitter_id"], ["user.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "registration_number",
            name="unique_registration_numbers_among_company",
        ),
    )
    op.create_index(
        op.f("ix_vehicle_company_id"), "vehicle", ["company_id"], unique=False
    )
    op.add_column(
        "vehicle_booking", sa.Column("vehicle_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_vehicle_booking_vehicle_id"),
        "vehicle_booking",
        ["vehicle_id"],
        unique=False,
    )
    op.create_foreign_key(
        None, "vehicle_booking", "vehicle", ["vehicle_id"], ["id"]
    )

    _migrate_vehicles()
    op.alter_column("vehicle_booking", "vehicle_id", nullable=False)
    op.drop_column("vehicle_booking", "registration_number")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "vehicle_booking",
        sa.Column(
            "registration_number",
            sa.TEXT(),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_constraint(None, "vehicle_booking", type_="foreignkey")
    op.drop_index(
        op.f("ix_vehicle_booking_vehicle_id"), table_name="vehicle_booking"
    )
    op.drop_column("vehicle_booking", "vehicle_id")
    op.drop_index(op.f("ix_vehicle_company_id"), table_name="vehicle")
    op.drop_table("vehicle")
    # ### end Alembic commands ###
