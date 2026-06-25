"""add moving business type

Revision ID: 296651475830
Revises: ed3f60d26a7a
Create Date: 2026-06-25 14:48:35.039154

"""

from alembic import op
import sqlalchemy as sa

from app.models.business import TransportType, BusinessType

# revision identifiers, used by Alembic.
revision = "296651475830"
down_revision = "ed3f60d26a7a"
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
            "Déménagement",
            name="businesstype",
            native_enum=False,
        ),
        nullable=False,
    )

    data = [
        {
            "id": 10,
            "transport_type": TransportType.TRM,
            "business_type": BusinessType.MOVE,
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
    connection.execute(
        sa.text(
            "DELETE FROM business WHERE id = :id OR business_type = :business_type"
        ),
        {"id": 10, "business_type": BusinessType.MOVE.value},
    )

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
