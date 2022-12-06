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
      alter table address 
      add column new_address_id int4;

      update address a set new_address_id = r.new_address_id
      from (
        select geo_api_id, min(id) as new_address_id from address 
        where geo_api_id is not null 
        group by geo_api_id 
        having count(*) > 1
      ) as r 
      where a.geo_api_id is not null 
      and a.geo_api_id = r.geo_api_id
      and a.id <> r.new_address_id;

      alter table company_known_address
      add column new_address_id int4,
      add column new_company_known_address_id int4;

      update company_known_address set new_address_id = a.new_address_id
      from address a 
      where a.id = address_id and a.new_address_id is not null;

      update company_known_address set new_address_id = address_id 
      where new_address_id is null;

      update company_known_address cka set new_company_known_address_id = r.new_company_known_address_id
      from (
      select company_id, new_address_id, max(id) as new_company_known_address_id from company_known_address 
      group by company_id, new_address_id 
      having count(*) > 1
      ) as r 
      where cka.new_address_id = r.new_address_id
      and cka.company_id = r.company_id
      and r.new_company_known_address_id <> cka.id;

      update location_entry set address_id = a.new_address_id
      from address a 
      where a.id = address_id 
      and a.new_address_id is not null;

      update location_entry set company_known_address_id  = cka.new_company_known_address_id
      from company_known_address cka 
      where cka.id = company_known_address_id 
      and cka.new_company_known_address_id is not null 
      and cka.new_company_known_address_id <> company_known_address_id;

      delete from company_known_address 
      where new_company_known_address_id is not null;

      update company_known_address set address_id = new_address_id 
      where new_address_id <> address_id;

      delete from address 
      where new_address_id is not null;

      alter table address 
      drop column new_address_id;

      alter table company_known_address
      drop column new_address_id,
      drop column new_company_known_address_id;
      """
    )


def downgrade():
    # nothing to do
    pass
