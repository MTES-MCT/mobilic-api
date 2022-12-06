"""fix duplicate addresses

Revision ID: 52434978c99e
Revises: 660b542c1ed2
Create Date: 2022-12-06 10:28:35.437685

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "52434978c99e"
down_revision = "660b542c1ed2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE address 
        ADD COLUMN new_address_id int4;

        UPDATE address a SET new_address_id = r.new_address_id
        FROM (
          SELECT geo_api_id, min(id) AS new_address_id FROM address 
          WHERE geo_api_id IS NOT NULL 
          GROUP BY geo_api_id 
          HAVING COUNT(*) > 1
        ) AS r 
        WHERE a.geo_api_id IS NOT NULL 
        AND a.geo_api_id = r.geo_api_id
        AND a.id <> r.new_address_id;

        ALTER TABLE company_known_address
        ADD COLUMN new_address_id int4,
        ADD COLUMN new_company_known_address_id int4;

        UPDATE company_known_address SET new_address_id = a.new_address_id
        FROM address a 
        WHERE a.id = address_id AND a.new_address_id IS NOT NULL;

        UPDATE company_known_address SET new_address_id = address_id 
        WHERE new_address_id IS NULL;

        UPDATE company_known_address cka SET new_company_known_address_id = r.new_company_known_address_id
        FROM (
        SELECT company_id, new_address_id, max(id) AS new_company_known_address_id FROM company_known_address 
        GROUP BY company_id, new_address_id 
        HAVING COUNT(*) > 1
        ) AS r 
        WHERE cka.new_address_id = r.new_address_id
        AND cka.company_id = r.company_id
        AND r.new_company_known_address_id <> cka.id;

        UPDATE location_entry SET address_id = a.new_address_id
        FROM address a 
        WHERE a.id = address_id 
        AND a.new_address_id IS NOT NULL;

        UPDATE location_entry SET company_known_address_id  = cka.new_company_known_address_id
        FROM company_known_address cka 
        WHERE cka.id = company_known_address_id 
        AND cka.new_company_known_address_id IS NOT NULL 
        AND cka.new_company_known_address_id <> company_known_address_id;

        DELETE FROM company_known_address 
        WHERE new_company_known_address_id IS NOT NULL;

        UPDATE company_known_address SET address_id = new_address_id 
        WHERE new_address_id <> address_id;

        DELETE FROM address 
        WHERE new_address_id IS NOT NULL;

        ALTER TABLE address 
        DROP COLUMN new_address_id;

        ALTER TABLE company_known_address
        DROP COLUMN new_address_id,
        DROP COLUMN new_company_known_address_id;
        """
    )


def downgrade():
    # nothing to do
    pass
