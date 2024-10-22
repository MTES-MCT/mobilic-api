"""add taxi businesses

Revision ID: bd643a8d5269
Revises: 0d842a23583f
Create Date: 2024-10-22 12:03:34.022199

"""
from alembic import op
import sqlalchemy as sa

from app.models.business import TransportType, BusinessType

# revision identifiers, used by Alembic.
revision = "bd643a8d5269"
down_revision = "0d842a23583f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE business DROP CONSTRAINT IF EXISTS businesstype")
    op.alter_column(
        "business",
        "business_type",
        type_=sa.Enum(
            "Longue distance",
            "Courte distance",
            "Messagerie, Fonds et valeur",
            "Lignes régulières",
            "Occasionnels",
            "Taxi général",
            "Taxi conventionné",
            "VTC",
            "LOTI",
            name="businesstype",
            native_enum=False,
        ),
        nullable=False,
    )

    data = [
        {
            "id": 6,
            "transport_type": TransportType.TRV,
            "business_type": BusinessType.TAXI_GENERAL,
        },
        {
            "id": 7,
            "transport_type": TransportType.TRV,
            "business_type": BusinessType.TAXI_REGULATED,
        },
        {
            "id": 8,
            "transport_type": TransportType.TRV,
            "business_type": BusinessType.VTC,
        },
        {
            "id": 9,
            "transport_type": TransportType.TRV,
            "business_type": BusinessType.LOTI,
        },
    ]

    connection = op.get_bind()
    connection.execute(
        sa.insert(
            sa.Table("business", sa.MetaData(), autoload_with=connection)
        ).values(data)
    )


def downgrade():
    op.execute("ALTER TABLE business DROP CONSTRAINT IF EXISTS businesstype")
    op.alter_column(
        "business",
        "business_type",
        type_=sa.Enum(
            "Longue distance",
            "Courte distance",
            "Messagerie, Fonds et valeur",
            "Lignes régulières",
            "Occasionnels",
            name="businesstype",
            native_enum=False,
        ),
        nullable=False,
    )
