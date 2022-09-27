"""add_user_timezone_name

Revision ID: 22a0e898310e
Revises: 2c97929c18d0
Create Date: 2022-09-01 17:33:48.818171

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "22a0e898310e"
down_revision = "2c97929c18d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("timezone_name", sa.String(length=255)))
    op.execute("UPDATE \"user\" SET timezone_name = 'Europe/Paris'")
    op.execute(
        """
      UPDATE \"user\" 
      SET timezone_name = request.tz 
      FROM 
      (
        SELECT 
          user_id, 
          CASE 
            WHEN cp = '984' THEN 'Indian/Kerguelen'
            WHEN cp = '986' THEN 'Pacific/Wallis'
            WHEN cp = '987' THEN 'Pacific/Tahiti'
            WHEN cp = '988' THEN 'Pacific/Noumea'
            WHEN cp = '971' THEN 'America/Guadeloupe'
            WHEN cp = '972' THEN 'America/Martinique'
            WHEN cp = '973' THEN 'America/Cayenne'
            WHEN cp = '974' THEN 'Indian/Reunion'
            WHEN cp = '975' THEN 'America/Miquelon'
            WHEN cp = '976' THEN 'Indian/Mayotte'
          END AS tz
        FROM (
          SELECT distinct on(user_id) user_id, substring(postal_code,0,4) AS cp 
          FROM address ad 
          INNER JOIN location_entry loc ON ad.id = loc.address_id 
          INNER JOIN activity ac ON ac.mission_id = loc.mission_id
          ORDER BY user_id, loc.creation_time desc, postal_code) AS inside_request
          WHERE cp like '97%' or cp like '98%'
      ) AS request
      WHERE id = request.user_id
      """
    )
    op.alter_column("user", "timezone_name", nullable=False)


def downgrade():
    op.drop_column("user", "timezone_name")
