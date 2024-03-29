"""ajout champ last_submitter_id dans activity

Revision ID: 915e0942f14f
Revises: 6bfdb39b721f
Create Date: 2022-02-15 11:02:33.733812

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session

# revision identifiers, used by Alembic.
revision = "915e0942f14f"
down_revision = "6bfdb39b721f"
branch_labels = None
depends_on = None


def _migrate_activities():
    session = Session(bind=op.get_bind())
    session.execute(
        """
        UPDATE activity a
        SET last_submitter_id = (
            SELECT av.submitter_id
            FROM activity_version av
            WHERE (av.version_number = (
                    SELECT MAX(av2.version_number)
                    FROM activity_version av2
                    WHERE av2.activity_id = a.id
                    )
                )
            AND (av.activity_id = a.id)
        )
        """
    )


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "activity", sa.Column("last_submitter_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "activity_last_submitter_id_fkey",
        "activity",
        "user",
        ["last_submitter_id"],
        ["id"],
    )
    # ### end Alembic commands ###

    _migrate_activities()


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "activity_last_submitter_id_fkey", "activity", type_="foreignkey"
    )
    op.drop_column("activity", "last_submitter_id")
    # ### end Alembic commands ###
