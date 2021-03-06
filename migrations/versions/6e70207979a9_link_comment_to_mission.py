"""Link comment to mission

Revision ID: 6e70207979a9
Revises: f61f00cde16f
Create Date: 2020-04-28 15:13:00.404776

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm.session import Session
from collections import namedtuple, defaultdict

# revision identifiers, used by Alembic.
revision = "6e70207979a9"
down_revision = "f61f00cde16f"
branch_labels = None
depends_on = None


ActivityData = namedtuple(
    "ActivityData", ["submitter_id", "event_time", "mission_id"]
)
CommentData = namedtuple("CommentData", ["id", "submitter_id", "event_time"])


def _migrate_comments():
    session = Session(bind=op.get_bind())
    session.execute("DELETE FROM comment WHERE submitter_id != user_id")
    activities = session.execute(
        """
        SELECT a.submitter_id, a.event_time, a.mission_id
        FROM activity a
        """
    )
    activities = sorted(
        [ActivityData(*a) for a in activities], key=lambda a: a.event_time
    )
    activities_per_submitter = defaultdict(list)
    for activity in activities:
        activities_per_submitter[activity.submitter_id].append(activity)

    comments = session.execute(
        """
        SELECT id, submitter_id, event_time
        FROM comment
        """
    )
    for comment in comments:
        submitter_activities = activities_per_submitter[comment.submitter_id]
        related_activities = [
            a
            for a in submitter_activities
            if a.event_time <= comment.event_time
        ]
        if not related_activities:
            session.execute(
                "DELETE from comment WHERE id = :id", dict(id=comment.id)
            )
        else:
            latest_activity = related_activities[-1]
            session.execute(
                "UPDATE comment SET mission_id = :mission_id WHERE id = :id",
                dict(id=comment.id, mission_id=latest_activity.mission_id),
            )


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "comment", sa.Column("mission_id", sa.Integer(), nullable=True)
    )

    _migrate_comments()

    op.drop_constraint("comment_user_id_fkey", "comment", type_="foreignkey")
    op.alter_column("comment", "mission_id", nullable=False)
    op.create_index(
        op.f("ix_comment_mission_id"), "comment", ["mission_id"], unique=False
    )
    op.drop_index("ix_comment_user_id", table_name="comment")
    op.drop_column("comment", "user_id")
    op.create_foreign_key(None, "comment", "mission", ["mission_id"], ["id"])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "comment",
        sa.Column("user_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.execute("""UPDATE comment SET user_id = submitter_id""")
    op.alter_column("comment", "user_id", nullable=False)

    # op.drop_constraint(None, 'comment', type_='foreignkey')
    op.create_foreign_key(
        "comment_user_id_fkey", "comment", "user", ["user_id"], ["id"]
    )
    op.create_index("ix_comment_user_id", "comment", ["user_id"], unique=False)
    op.drop_index(op.f("ix_comment_mission_id"), table_name="comment")
    op.drop_column("comment", "mission_id")
    # ### end Alembic commands ###
