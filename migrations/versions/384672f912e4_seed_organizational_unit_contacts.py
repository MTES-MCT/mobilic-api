"""seed_organizational_unit_contacts

Revision ID: 384672f912e4
Revises: 67d7cbf16078
Create Date: 2026-10-27 00:00:00.000000

"""

import csv
from datetime import datetime
from pathlib import Path

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "384672f912e4"
down_revision = "67d7cbf16078"
branch_labels = None
depends_on = None

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "organizational_unit_contacts.csv"
)

organizational_unit_contact_table = sa.table(
    "organizational_unit_contact",
    sa.column("creation_time", sa.DateTime),
    sa.column("organizational_unit", sa.String),
    sa.column("address", sa.String),
    sa.column("email", sa.String),
    sa.column("phone_number", sa.String),
)


def _load_rows():
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return [
            {key: value or None for key, value in row.items()}
            for row in csv.DictReader(f)
        ]


def upgrade():
    now = datetime.utcnow()
    op.bulk_insert(
        organizational_unit_contact_table,
        [dict(row, creation_time=now) for row in _load_rows()],
    )


def downgrade():
    op.execute(
        organizational_unit_contact_table.delete().where(
            organizational_unit_contact_table.c.organizational_unit.in_(
                [row["organizational_unit"] for row in _load_rows()]
            )
        )
    )
