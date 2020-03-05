"""Make context a set field

Revision ID: 76530c01c430
Revises: ad96684d50e1
Create Date: 2020-03-05 12:59:08.547240

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "76530c01c430"
down_revision = "ad96684d50e1"


def upgrade():
    op.add_column(
        "activity",
        sa.Column("_context", sa.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.execute(
        """
        UPDATE activity SET _context = 
            CASE WHEN context is null THEN null 
            ELSE ARRAY[context] END
    """
    )
    op.drop_column("activity", "context")
    op.add_column(
        "activity",
        sa.Column("context", sa.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.execute(
        """
        UPDATE activity SET context = _context
    """
    )
    op.drop_column("activity", "_context")

    op.add_column(
        "expenditure",
        sa.Column("_context", sa.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.execute(
        """
            UPDATE expenditure SET _context = 
                CASE WHEN context is null THEN null 
                ELSE ARRAY[context] END
        """
    )
    op.drop_column("expenditure", "context")
    op.add_column(
        "expenditure",
        sa.Column("context", sa.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.execute(
        """
            UPDATE expenditure SET context = _context
        """
    )
    op.drop_column("expenditure", "_context")

    op.add_column(
        "comment",
        sa.Column("_context", sa.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.execute(
        """
            UPDATE comment SET _context = 
                CASE WHEN context is null THEN null 
                ELSE ARRAY[context] END
        """
    )
    op.drop_column("comment", "context")
    op.add_column(
        "comment",
        sa.Column("context", sa.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.execute(
        """
            UPDATE comment SET context = _context
        """
    )
    op.drop_column("comment", "_context")


def downgrade():
    op.add_column(
        "activity", sa.Column("_context", sa.String(length=255), nullable=True)
    )
    op.execute(
        """
            UPDATE activity SET _context = 
                CASE WHEN context is null THEN null 
                ELSE context[1] END
        """
    )
    op.drop_column("activity", "context")
    op.add_column(
        "activity",
        sa.Column(
            "context",
            sa.Enum(
                "conflicting_with_history",
                "no_activity_switch",
                "driver_switch",
                "unauthorized_submitter",
                name="activitycontext",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
            UPDATE activity SET context = _context
        """
    )
    op.drop_column("activity", "_context")

    op.add_column(
        "expenditure",
        sa.Column("_context", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
                UPDATE expenditure SET _context = 
                    CASE WHEN context is null THEN null 
                    ELSE context[1] END
            """
    )
    op.drop_column("expenditure", "context")
    op.add_column(
        "expenditure",
        sa.Column(
            "context",
            sa.Enum(
                "unauthorized_submitter",
                name="eventbasecontext",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
                UPDATE expenditure SET context = _context
            """
    )
    op.drop_column("expenditure", "_context")

    op.add_column(
        "comment", sa.Column("_context", sa.String(length=255), nullable=True)
    )
    op.execute(
        """
                UPDATE comment SET _context = 
                    CASE WHEN context is null THEN null 
                    ELSE context[1] END
            """
    )
    op.drop_column("comment", "context")
    op.add_column(
        "comment",
        sa.Column(
            "context",
            sa.Enum(
                "unauthorized_submitter",
                name="eventbasecontext",
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
                UPDATE comment SET context = _context
            """
    )
    op.drop_column("comment", "_context")
