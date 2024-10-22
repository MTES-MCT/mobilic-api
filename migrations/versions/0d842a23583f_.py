"""Add get_companies_status for sync_brevo

Revision ID: 0d842a23583f
Revises: 83a7fd4629f0
Create Date: 2024-10-15 11:36:03.770348

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0d842a23583f"
down_revision = "83a7fd4629f0"
branch_labels = None
depends_on = None


def upgrade():

    conn = op.get_bind()
    conn.execute(
        """
        BEGIN;
        CREATE OR REPLACE FUNCTION get_companies_status()
        RETURNS TABLE (
            company_id INT,
            usual_name TEXT,
            siren TEXT,
            phone_number TEXT,
            min_effective_range INT,
            naf_code TEXT,
            status TEXT,
            status_date TEXT,
            company_creation_date TEXT,
            last_mission_reception_date TEXT,
            mission_count_last_month INT,
            admin_email TEXT,
            admin_first_name TEXT,
            admin_last_name TEXT
        ) AS $$
        BEGIN
            RETURN QUERY
            WITH ranked_missions AS (
                SELECT
                    c.id AS company_id,
                    m.id AS mission_id,
                    m.reception_time AS mission_reception_time,
                    ROW_NUMBER() OVER (PARTITION BY c.id ORDER BY m.reception_time DESC) AS row_num
                FROM
                    company_stats cs
                    JOIN company c ON c.id = cs.company_id
                    LEFT JOIN mission m ON c.id = m.company_id
            ),
            counts AS (
                SELECT
                    ranked_missions.company_id,
                    COUNT(*) AS mission_count_last_month
                FROM
                    ranked_missions
                WHERE
                    ranked_missions.mission_reception_time >= NOW() - INTERVAL '1 months'
                GROUP BY
                    ranked_missions.company_id
            ),
            closest_admin_users AS (
                SELECT
                    rm.company_id,
                    u.id AS user_id,
                    u.email AS admin_email,
                    INITCAP(u.first_name) AS admin_first_name,
                    INITCAP(u.last_name) AS admin_last_name,
                    ABS(EXTRACT(epoch FROM ea.creation_time - c.creation_time)) AS difference_seconds,
                    ROW_NUMBER() OVER (PARTITION BY rm.company_id ORDER BY ABS(EXTRACT(epoch FROM ea.creation_time - c.creation_time))) AS row_num,
                    ea.has_admin_rights 
                FROM
                    "user" u
                JOIN 
                    employment ea ON u.id = ea.user_id
                    AND ea.has_admin_rights IS TRUE
                    AND ea.validation_status = 'approved'
                    AND ea.end_date IS NULL
                    AND ea.dismissed_at IS NULL
                JOIN 
                    ranked_missions rm ON ea.company_id = rm.company_id
                JOIN 
                    company c ON c.id = rm.company_id
            )
            SELECT 
                c.id AS company_id,
                c.usual_name::TEXT AS usual_name,
                (CASE WHEN c.siren IS NULL THEN '0' ELSE c.siren END)::TEXT AS siren,
                c.phone_number::TEXT AS phone_number,
                CASE
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '00' THEN 0
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '01' THEN 1
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '02' THEN 3
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '03' THEN 6
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '11' THEN 10
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '12' THEN 20
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '21' THEN 50
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '22' THEN 100
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '31' THEN 200
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '32' THEN 250
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '41' THEN 500
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '42' THEN 1000
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '51' THEN 2000
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '52' THEN 5000
                    WHEN (c.siren_api_info#>> array['uniteLegale', 'trancheEffectifsUniteLegale']::text[])::text = '53' THEN 10000
                    ELSE 0
                END AS min_effective_range,
                COALESCE(c.siren_api_info#>> array['uniteLegale', 'activitePrincipaleUniteLegale']::text[], 'NA')::TEXT AS naf_code,
                CASE
                    WHEN cs.first_certification_date IS NOT NULL THEN 'Certifiée'
                    WHEN cs.first_active_criteria_date IS NOT NULL THEN 'Activé' 
                    WHEN cs.first_mission_validation_by_admin_date IS NOT NULL AND counts.mission_count_last_month >= 1 THEN
                        'Onboardée et actif'
                    WHEN cs.first_mission_validation_by_admin_date IS NOT NULL AND counts.mission_count_last_month = 0 THEN
                        'Onboardée et inactif'
                    WHEN cs.first_employee_invitation_date IS NOT NULL THEN 'Salarié invité'
                    ELSE 'Inscrite'
                END AS status,
                CASE 
                    WHEN cs.first_certification_date IS NOT NULL THEN TO_CHAR(cs.first_certification_date, 'DD/MM/YYYY')
                    WHEN cs.first_active_criteria_date IS NOT NULL THEN TO_CHAR(cs.first_active_criteria_date, 'DD/MM/YYYY')
                    WHEN cs.first_mission_validation_by_admin_date IS NOT NULL THEN TO_CHAR(cs.first_mission_validation_by_admin_date, 'DD/MM/YYYY')
                    WHEN cs.first_employee_invitation_date IS NOT NULL THEN TO_CHAR(cs.first_employee_invitation_date, 'DD/MM/YYYY')
                    ELSE TO_CHAR(cs.creation_time, 'DD/MM/YYYY')
                END AS status_date,
                TO_CHAR(c.creation_time, 'DD/MM/YYYY') AS company_creation_date,
                COALESCE(TO_CHAR(rm.mission_reception_time, 'DD/MM/YYYY'), 'NA') AS last_mission_reception_date,
                COALESCE(counts.mission_count_last_month, 0)::int AS mission_count_last_month,
                MAX(cau.admin_email)::TEXT AS admin_email,
                MAX(cau.admin_first_name)::TEXT AS admin_first_name,
                MAX(cau.admin_last_name)::TEXT AS admin_last_name
            FROM
                company c
                LEFT JOIN company_stats cs ON c.id = cs.company_id
                LEFT JOIN ranked_missions rm ON c.id = rm.company_id
                LEFT JOIN counts ON c.id = counts.company_id
                LEFT JOIN closest_admin_users cau ON rm.company_id = cau.company_id AND cau.row_num = 1
            WHERE
                rm.row_num = 1
            GROUP BY
                c.id, c.usual_name, counts.mission_count_last_month, cs.first_certification_date, cs.first_active_criteria_date, cs.first_employee_invitation_date, cs.creation_time, rm.mission_reception_time, cs.first_mission_validation_by_admin_date
            ORDER BY
                c.id;
        END;
        $$ LANGUAGE plpgsql STABLE;
        COMMIT;
    """
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("DROP FUNCTION get_companies_status()")
    # ### end Alembic commands ###
