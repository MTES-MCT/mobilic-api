"""create business table

Revision ID: aa1096a64d0f
Revises: c452a761d31a
Create Date: 2024-06-05 13:48:20.177923

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

from app.models.business import TransportType, BusinessType

# revision identifiers, used by Alembic.
revision = "aa1096a64d0f"
down_revision = "c452a761d31a"
branch_labels = None
depends_on = None


def upgrade():
    business_table = op.create_table(
        "business",
        sa.Column(
            "creation_time",
            sa.DateTime(),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "transport_type",
            sa.Enum(
                "Marchandises",
                "Voyageurs",
                name="transporttype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "business_type",
            sa.Enum(
                "Longue distance",
                "Courte distance",
                "Messagerie, Fonds et valeur",
                "Lignes régulières",
                "Occasionnels",
                name="businesstype",
                native_enum=False,
            ),
            nullable=False,
            unique=True,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "company", sa.Column("business_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(None, "company", "business", ["business_id"], ["id"])
    op.add_column(
        "employment", sa.Column("business_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        None, "employment", "business", ["business_id"], ["id"]
    )

    op.bulk_insert(
        business_table,
        [
            {
                "id": 1,
                "transport_type": TransportType.TRM,
                "business_type": BusinessType.LONG_DISTANCE,
            },
            {
                "id": 2,
                "transport_type": TransportType.TRM,
                "business_type": BusinessType.SHORT_DISTANCE,
            },
            {
                "id": 3,
                "transport_type": TransportType.TRM,
                "business_type": BusinessType.SHIPPING,
            },
            {
                "id": 4,
                "transport_type": TransportType.TRV,
                "business_type": BusinessType.FREQUENT,
            },
            {
                "id": 5,
                "transport_type": TransportType.TRV,
                "business_type": BusinessType.INFREQUENT,
            },
        ],
    )


def downgrade():
    op.drop_constraint(
        "employment_business_id_fkey", "employment", type_="foreignkey"
    )
    op.drop_column("employment", "business_id")
    op.drop_constraint(
        "company_business_id_fkey", "company", type_="foreignkey"
    )
    op.drop_column("company", "business_id")
    op.drop_table("business")
