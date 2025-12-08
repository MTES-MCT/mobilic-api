from datetime import date, timedelta

from app import db
from app.domain.certificate_criteria import compute_company_certifications
from app.domain.regulations_per_day import (
    EXTRA_NOT_ENOUGH_BREAK,
    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
)
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
from app.models.regulation_check import RegulationCheckType
from app.seed.scenarios.certificated_company import (
    BRONZE_COMPANY_NAME,
    SILVER_COMPANY_NAME,
    GOLD_COMPANY_NAME,
    DIAMOND_COMPANY_NAME,
    NO_CERTIF_COMPANY_NAME,
    AVERAGE_1_COMPANY_NAME,
    AVERAGE_2_COMPANY_NAME,
)


def scenario_run_certificate():
    compute_company_certifications(date.today())

    CompanyCertification.query.filter(
        CompanyCertification.company_id.in_(
            db.session.query(Company.id).filter(
                Company.usual_name.in_(
                    [
                        BRONZE_COMPANY_NAME,
                        SILVER_COMPANY_NAME,
                        GOLD_COMPANY_NAME,
                        DIAMOND_COMPANY_NAME,
                        AVERAGE_2_COMPANY_NAME,
                        AVERAGE_1_COMPANY_NAME,
                    ]
                )
            )
        )
    ).delete(synchronize_session=False)
    db.session.commit()

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
    company_average_1 = Company.query.filter(
        Company.usual_name == AVERAGE_1_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=0.75,
            admin_changes=0.15,
            compliancy=3,
            company_id=company_average_1.id,
            info={
                "alerts": [
                    {"type": RegulationCheckType.MINIMUM_DAILY_REST},
                    {"type": RegulationCheckType.MAXIMUM_WORK_DAY_TIME},
                    {"type": RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK},
                ]
            },
        )
    )
    company_average_2 = Company.query.filter(
        Company.usual_name == AVERAGE_2_COMPANY_NAME
    ).first()
    db.session.add(
        CompanyCertification(
            attribution_date=attribution_date,
            expiration_date=expiration_date,
            log_in_real_time=0.40,
            admin_changes=0.30,
            compliancy=1,
            company_id=company_average_2.id,
            info={
                "alerts": [
                    {"type": RegulationCheckType.MINIMUM_DAILY_REST},
                    {"type": RegulationCheckType.MAXIMUM_WORK_DAY_TIME},
                    {"type": RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK},
                    {
                        "type": RegulationCheckType.ENOUGH_BREAK,
                        "extra_field": EXTRA_NOT_ENOUGH_BREAK,
                    },
                    {
                        "type": RegulationCheckType.ENOUGH_BREAK,
                        "extra_field": EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
                    },
                ]
            },
        )
    )
