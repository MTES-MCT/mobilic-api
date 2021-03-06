"""Set foreign key on revisee to allow multiple revisions of the same event

Revision ID: 46be945ea269
Revises: 1517112ecb4d
Create Date: 2020-03-11 18:26:27.461555

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "46be945ea269"
down_revision = "1517112ecb4d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "activity", sa.Column("revisee_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_activity_revisee_id"),
        "activity",
        ["revisee_id"],
        unique=False,
    )
    op.execute(
        """
        UPDATE activity a set revisee_id = a2.id
        FROM activity a2 where a.id = a2.revised_by_id
    """
    )
    op.drop_index("ix_activity_revised_by_id", table_name="activity")
    op.drop_constraint(
        "activity_revised_by_id_fkey", "activity", type_="foreignkey"
    )
    op.create_foreign_key(None, "activity", "activity", ["revisee_id"], ["id"])
    op.drop_column("activity", "revised_at")
    op.drop_column("activity", "revised_by_id")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "activity",
        sa.Column(
            "revised_by_id", sa.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "activity",
        sa.Column(
            "revised_at",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.execute(
        """
            UPDATE activity a set revised_by_id = a2.id
            FROM activity a2 where a.id = a2.revisee_id;
            UPDATE activity set revised_at = event_time
            WHERE revised_by_id is not null;
        """
    )
    op.drop_constraint(None, "activity", type_="foreignkey")
    op.create_foreign_key(
        "activity_revised_by_id_fkey",
        "activity",
        "activity",
        ["revised_by_id"],
        ["id"],
    )
    op.create_index(
        "ix_activity_revised_by_id",
        "activity",
        ["revised_by_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_activity_revisee_id"), table_name="activity")
    op.drop_column("activity", "revisee_id")
    # ### end Alembic commands ###
