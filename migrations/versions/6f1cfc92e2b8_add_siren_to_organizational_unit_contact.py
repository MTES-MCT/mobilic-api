"""add_siren_to_organizational_unit_contact

Revision ID: 6f1cfc92e2b8
Revises: 384672f912e4
Create Date: 2026-10-28 15:58:04.052811

"""

import csv
from pathlib import Path

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f1cfc92e2b8"
down_revision = "384672f912e4"
branch_labels = None
depends_on = None

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "organizational_unit_contacts.csv"
)

organizational_unit_contact_table = sa.table(
    "organizational_unit_contact",
    sa.column("organizational_unit", sa.String),
    sa.column("siren", sa.String),
)


def _load_sirens():
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return {
            row["organizational_unit"]: row["siren"] or None
            for row in csv.DictReader(f)
        }


def upgrade():
    op.add_column(
        "organizational_unit_contact",
        sa.Column("siren", sa.String(length=9), nullable=True),
    )
    connection = op.get_bind()
    for organizational_unit, siren in _load_sirens().items():
        if siren is None:
            continue
        connection.execute(
            organizational_unit_contact_table.update()
            .where(
                organizational_unit_contact_table.c.organizational_unit
                == organizational_unit
            )
            .values(siren=siren)
        )


def downgrade():
    op.drop_column("organizational_unit_contact", "siren")
