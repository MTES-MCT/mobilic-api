from datetime import date, timedelta

from app import db
from app.domain.certificate_criteria import compute_company_certifications
from app.helpers.time import previous_month_period
from app.models import CompanyCertification, Company
from app.models.company_certification import (
    CERTIFICATION_REAL_TIME_BRONZE,
    CERTIFICATION_ADMIN_CHANGES_BRONZE,
    CERTIFICATION_ADMIN_CHANGES_SILVER,
    CERTIFICATION_REAL_TIME_SILVER,
    CERTIFICATION_COMPLIANCY_SILVER,
    CERTIFICATION_REAL_TIME_GOLD,
    CERTIFICATION_ADMIN_CHANGES_GOLD,
    CERTIFICATION_COMPLIANCY_GOLD,
    CERTIFICATION_REAL_TIME_DIAMOND,
    CERTIFICATION_ADMIN_CHANGES_DIAMOND,
    CERTIFICATION_COMPLIANCY_DIAMOND,
)
from app.seed.scenarios.certificated_company import (
    BRONZE_COMPANY_NAME,
    SILVER_COMPANY_NAME,
    GOLD_COMPANY_NAME,
    DIAMOND_COMPANY_NAME,
    NO_CERTIF_COMPANY_NAME,
)


def scenario_run_certificate():
    compute_company_certifications(date.today())

    # create fake certificate results
    attribution_date, expiration_date = previous_month_period(date.today())
    expiration_date = expiration_date + timedelta(days=31)

    company_bronze = Company.query.filter(
        Company.usual_name == BRONZE_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=CERTIFICATION_REAL_TIME_BRONZE,
            admin_changes=CERTIFICATION_ADMIN_CHANGES_BRONZE,
            compliancy=0,
            company_id=company_bronze.id,
        )
    )
    company_silver = Company.query.filter(
        Company.usual_name == SILVER_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=CERTIFICATION_REAL_TIME_SILVER,
            admin_changes=CERTIFICATION_ADMIN_CHANGES_SILVER,
            compliancy=CERTIFICATION_COMPLIANCY_SILVER,
            company_id=company_silver.id,
        )
    )
    company_gold = Company.query.filter(
        Company.usual_name == GOLD_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=CERTIFICATION_REAL_TIME_GOLD,
            admin_changes=CERTIFICATION_ADMIN_CHANGES_GOLD,
            compliancy=CERTIFICATION_COMPLIANCY_GOLD,
            company_id=company_gold.id,
        )
    )
    company_diamond = Company.query.filter(
        Company.usual_name == DIAMOND_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=CERTIFICATION_REAL_TIME_DIAMOND,
            admin_changes=CERTIFICATION_ADMIN_CHANGES_DIAMOND,
            compliancy=CERTIFICATION_COMPLIANCY_DIAMOND,
            company_id=company_diamond.id,
        )
    )
    company_no_certif = Company.query.filter(
        Company.usual_name == NO_CERTIF_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=CERTIFICATION_REAL_TIME_DIAMOND,
            admin_changes=1.0,
            compliancy=4,
            company_id=company_no_certif.id,
        )
    )
