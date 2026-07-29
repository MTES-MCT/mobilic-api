"""add moving transport type

Revision ID: e5d78113a5ac
Revises: 0da0a33704b0
Create Date: 2026-07-29 13:23:04.798404

"""

from app import db
from alembic import op
import sqlalchemy as sa
from app.models.business import TransportType, BusinessType

# revision identifiers, used by Alembic.
revision = "e5d78113a5ac"
down_revision = "0da0a33704b0"
branch_labels = None
depends_on = None


def upgrade():
    db.session.remove()
    op.execute(
        "ALTER TABLE business DROP CONSTRAINT IF EXISTS business_business_type_key"
    )
    op.execute("ALTER TABLE business DROP CONSTRAINT IF EXISTS transporttype")
    op.alter_column(
        "business",
        "transport_type",
        type_=sa.Enum(
            "Marchandises",
            "Voyageurs",
            "Déménagement",
            name="transporttype",
            native_enum=False,
        ),
        nullable=False,
    )

    # Replace unique constraint on business_type alone with (transport_type, business_type)
    op.create_unique_constraint(
        "business_transport_type_business_type_key",
        "business",
        ["transport_type", "business_type"],
    )

    data = [
        {
            "id": 10,
            "transport_type": TransportType.DEM,
            "business_type": BusinessType.LONG_DISTANCE,
        },
        {
            "id": 11,
            "transport_type": TransportType.DEM,
            "business_type": BusinessType.SHORT_DISTANCE,
        },
    ]

    connection = op.get_bind()
    connection.execute(
        sa.insert(
            sa.Table("business", sa.MetaData(), autoload_with=connection)
        ).values(data)
    )


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM business WHERE id IN (10, 11)"))

    op.execute(
        "ALTER TABLE business DROP CONSTRAINT IF EXISTS business_transport_type_business_type_key"
    )
    op.create_unique_constraint(
        "business_business_type_key",
        "business",
        ["business_type"],
    )

    op.execute("ALTER TABLE business DROP CONSTRAINT IF EXISTS transporttype")
    op.alter_column(
        "business",
        "transport_type",
        type_=sa.Enum(
            "Marchandises",
            "Voyageurs",
            name="transporttype",
            native_enum=False,
        ),
        nullable=False,
    )
