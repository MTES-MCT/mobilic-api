"""add file_content to export

Revision ID: 6bea1eb11e5e
Revises: a7f2c9e4b831
Create Date: 2026-10-19 13:28:50.600237

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6bea1eb11e5e"
down_revision = "a7f2c9e4b831"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "export", sa.Column("file_content", sa.LargeBinary(), nullable=True)
    )
    op.execute(
        "ALTER TABLE export ALTER COLUMN file_content SET STORAGE EXTERNAL"
    )


def downgrade():
    op.drop_column("export", "file_content")
