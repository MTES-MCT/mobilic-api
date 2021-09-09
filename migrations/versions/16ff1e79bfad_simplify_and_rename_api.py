"""simplify and rename API

Revision ID: 16ff1e79bfad
Revises: 83f49fddbcb6
Create Date: 2020-07-13 15:00:52.540885

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session
from collections import namedtuple


# revision identifiers, used by Alembic.
revision = "16ff1e79bfad"
down_revision = "83f49fddbcb6"
branch_labels = None
depends_on = None


def _migrate_vehicle_bookings():
    session = Session(bind=op.get_bind())

    session.execute(
        """
        WITH missions_with_vehicle_bookings AS (
            SELECT m.id, vb.vehicle_id, vb.event_time, ROW_NUMBER() OVER(PARTITION BY m.id ORDER BY vb.event_time DESC) AS rn
            FROM mission m
            JOIN vehicle_booking vb ON m.id = vb.mission_id
        ),
        missions_with_latest_vehicle_booking AS (
            SELECT id, vehicle_id
            FROM missions_with_vehicle_bookings
            WHERE rn = 1 AND vehicle_id is not null
        )
        UPDATE mission SET context = jsonb_build_object('vehicle_id', mwlvb.vehicle_id)
        FROM missions_with_latest_vehicle_booking mwlvb WHERE mission.id = mwlvb.id
        """
    )

    op.drop_index(
        "ix_vehicle_booking_mission_id", table_name="vehicle_booking"
    )
    op.drop_index(
        "ix_vehicle_booking_submitter_id", table_name="vehicle_booking"
    )
    op.drop_index(
        "ix_vehicle_booking_vehicle_id", table_name="vehicle_booking"
    )
    op.drop_table("vehicle_booking")


def _migrate_activities():
    op.add_column(
        "activity",
        sa.Column(
            "context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "dismiss_context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "activity", sa.Column("reception_time", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "activity",
        sa.Column(
            "revision_context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "activity", sa.Column("start_time", sa.DateTime(), nullable=True)
    )

    op.execute("UPDATE activity SET start_time = user_time")
    op.execute(
        "UPDATE activity set context = jsonb_build_object('comment', creation_comment) WHERE creation_comment is not null"
    )
    op.execute(
        "UPDATE activity set dismiss_context = jsonb_build_object('comment', dismiss_comment) WHERE dismiss_comment is not null"
    )
    op.execute(
        "UPDATE activity set revision_context = jsonb_build_object('comment', revision_comment) WHERE revision_comment is not null"
    )
    op.execute("UPDATE activity set reception_time = event_time")

    op.alter_column("activity", "reception_time", nullable=False)
    op.alter_column("activity", "start_time", nullable=False)

    op.drop_constraint(
        "activity_driver_id_fkey", "activity", type_="foreignkey"
    )
    op.drop_column("activity", "creation_comment")
    op.drop_column("activity", "event_time")
    op.drop_column("activity", "user_time")
    op.drop_column("activity", "driver_id")
    op.drop_column("activity", "revision_comment")
    op.drop_column("activity", "is_driver_switch")
    op.drop_column("activity", "dismiss_comment")

    op.create_check_constraint(
        "activity_start_time_before_reception_time",
        "activity",
        "(reception_time >= start_time)",
    )


MissionData = namedtuple(
    "MissionData",
    ["id", "submitter_id", "expenditures", "end_time", "user_ids"],
)


def _migrate_missions_and_expenditures():
    op.add_column(
        "mission", sa.Column("company_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "mission", sa.Column("reception_time", sa.DateTime(), nullable=True)
    )
    op.create_index(
        op.f("ix_mission_company_id"), "mission", ["company_id"], unique=False
    )
    op.create_foreign_key(None, "mission", "company", ["company_id"], ["id"])

    op.execute("UPDATE mission SET reception_time = event_time")
    op.execute(
        """UPDATE mission SET company_id = u.company_id FROM "user" u WHERE mission.submitter_id = u.id"""
    )
    op.alter_column("mission", "company_id", nullable=False)
    op.alter_column("mission", "reception_time", nullable=False)
    op.drop_column("mission", "event_time")

    op.create_table(
        "expenditure",
        sa.Column("creation_time", sa.DateTime(), nullable=False),
        sa.Column("reception_time", sa.DateTime(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "dismiss_type",
            sa.Enum("user_cancel", name="dismisstype", native_enum=False),
            nullable=True,
        ),
        sa.Column("dismiss_received_at", sa.DateTime(), nullable=True),
        sa.Column(
            "dismiss_context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "day_meal",
                "night_meal",
                "sleep_over",
                "snack",
                name="expendituretype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dismiss_author_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(dismiss_type != 'user_cancel' OR dismiss_author_id is not null)",
            name="non_nullable_dismiss_author_id",
        ),
        sa.CheckConstraint(
            "((dismissed_at is not null)::bool = (dismiss_type is not null)::bool AND (dismiss_type is not null)::bool = (dismiss_received_at is not null)::bool)",
            name="non_nullable_dismiss_type",
        ),
        sa.ForeignKeyConstraint(
            ["dismiss_author_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["mission.id"],
        ),
        sa.ForeignKeyConstraint(
            ["submitter_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_expenditure_dismiss_author_id"),
        "expenditure",
        ["dismiss_author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_expenditure_mission_id"),
        "expenditure",
        ["mission_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_expenditure_submitter_id"),
        "expenditure",
        ["submitter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_expenditure_user_id"),
        "expenditure",
        ["user_id"],
        unique=False,
    )

    session = Session(bind=op.get_bind())

    missions = session.execute(
        """
        WITH ma AS (
            SELECT m.submitter_id, m.id, m.expenditures, a.reception_time, a.user_id
            FROM mission m
            JOIN activity a ON m.id = a.mission_id
        )
        SELECT id, submitter_id, expenditures, max(reception_time) AS end_time, array_agg(user_id) AS user_ids
        FROM ma
        GROUP BY 1, 2, 3
        """
    )

    missions = [MissionData(*m) for m in missions]

    for mission in missions:
        if mission.expenditures:
            for exp, count in mission.expenditures.items():
                if count > 0:
                    for uid in set(mission.user_ids):
                        session.execute(
                            """
                            INSERT INTO expenditure(
                                creation_time,
                                reception_time,
                                type,
                                mission_id,
                                submitter_id,
                                user_id
                            )
                            VALUES(
                                NOW(),
                                :end_time,
                                :type,
                                :mission_id,
                                :submitter_id,
                                :user_id
                            )
                            """,
                            dict(
                                end_time=mission.end_time,
                                type=exp,
                                mission_id=mission.id,
                                submitter_id=mission.submitter_id,
                                user_id=uid,
                            ),
                        )

    op.drop_column("mission", "expenditures")


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_comment_dismiss_author_id", table_name="comment")
    op.drop_index("ix_comment_mission_id", table_name="comment")
    op.drop_index("ix_comment_submitter_id", table_name="comment")
    op.drop_table("comment")

    op.add_column(
        "mission",
        sa.Column(
            "context",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )

    _migrate_vehicle_bookings()

    _migrate_activities()

    _migrate_missions_and_expenditures()

    op.add_column(
        "mission_validation",
        sa.Column("reception_time", sa.DateTime(), nullable=True),
    )
    op.execute("UPDATE mission_validation SET reception_time = event_time")
    op.alter_column("mission_validation", "reception_time", nullable=False)
    op.drop_column("mission_validation", "event_time")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "mission_validation",
        sa.Column(
            "event_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_column("mission_validation", "reception_time")
    op.add_column(
        "mission",
        sa.Column(
            "expenditures",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "mission",
        sa.Column(
            "event_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_constraint(None, "mission", type_="foreignkey")
    op.drop_index(op.f("ix_mission_company_id"), table_name="mission")
    op.drop_column("mission", "reception_time")
    op.drop_column("mission", "context")
    op.drop_column("mission", "company_id")
    op.add_column(
        "activity",
        sa.Column(
            "dismiss_comment", sa.TEXT(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "is_driver_switch",
            sa.BOOLEAN(),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "revision_comment", sa.TEXT(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "driver_id", sa.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "user_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "event_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "creation_comment", sa.TEXT(), autoincrement=False, nullable=True
        ),
    )
    op.create_foreign_key(
        "activity_driver_id_fkey", "activity", "user", ["driver_id"], ["id"]
    )
    op.drop_column("activity", "start_time")
    op.drop_column("activity", "revision_context")
    op.drop_column("activity", "reception_time")
    op.drop_column("activity", "dismiss_context")
    op.drop_column("activity", "context")
    op.create_table(
        "vehicle_booking",
        sa.Column(
            "creation_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "event_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "submitter_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "user_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "vehicle_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
        sa.Column(
            "mission_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["mission.id"],
            name="vehicle_booking_mission_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["submitter_id"],
            ["user.id"],
            name="vehicle_booking_submitter_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicle.id"],
            name="vehicle_booking_vehicle_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="vehicle_booking_pkey"),
    )
    op.create_index(
        "ix_vehicle_booking_vehicle_id",
        "vehicle_booking",
        ["vehicle_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_booking_submitter_id",
        "vehicle_booking",
        ["submitter_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_booking_mission_id",
        "vehicle_booking",
        ["mission_id"],
        unique=False,
    )
    op.create_table(
        "comment",
        sa.Column(
            "creation_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "event_time",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("content", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "submitter_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "dismiss_author_id",
            sa.INTEGER(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "dismiss_type",
            sa.VARCHAR(length=22),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "dismissed_at",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "dismiss_received_at",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "dismiss_comment", sa.TEXT(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "mission_id", sa.INTEGER(), autoincrement=False, nullable=False
        ),
        sa.CheckConstraint(
            "((dismiss_type)::text <> 'user_cancel'::text) OR (dismiss_author_id IS NOT NULL)",
            name="non_nullable_dismiss_author_id",
        ),
        sa.CheckConstraint(
            "(dismiss_type)::text = ANY ((ARRAY['unauthorized_submitter'::character varying, 'user_cancel'::character varying])::text[])",
            name="dismisstype",
        ),
        sa.CheckConstraint(
            "((dismissed_at IS NOT NULL) = (dismiss_type IS NOT NULL)) AND ((dismiss_type IS NOT NULL) = (dismiss_received_at IS NOT NULL))",
            name="non_nullable_dismiss_type",
        ),
        sa.ForeignKeyConstraint(
            ["dismiss_author_id"],
            ["user.id"],
            name="comment_dismiss_author_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"], ["mission.id"], name="comment_mission_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["submitter_id"], ["user.id"], name="comment_submitter_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="comment_pkey"),
    )
    op.create_index(
        "ix_comment_submitter_id", "comment", ["submitter_id"], unique=False
    )
    op.create_index(
        "ix_comment_mission_id", "comment", ["mission_id"], unique=False
    )
    op.create_index(
        "ix_comment_dismiss_author_id",
        "comment",
        ["dismiss_author_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_expenditure_user_id"), table_name="expenditure")
    op.drop_index(
        op.f("ix_expenditure_submitter_id"), table_name="expenditure"
    )
    op.drop_index(op.f("ix_expenditure_mission_id"), table_name="expenditure")
    op.drop_index(
        op.f("ix_expenditure_dismiss_author_id"), table_name="expenditure"
    )
    op.drop_table("expenditure")
    # ### end Alembic commands ###
