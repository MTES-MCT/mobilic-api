from app import db
from app.models.company import Company
from app.models.company_certification import CompanyCertification
from app.models.company_stats import CompanyStats
from app.models.employment import Employment
from app.models.mission_validation import MissionValidation
from app.models.mission import Mission


def load_company_stats():
    companies = Company.query.all()
    for company in companies:
        company_stats = get_or_init_company_stats(company)
        for field, check in STEPS.items():
            if getattr(company_stats, field) is None:
                step_result = check(company.id)
                if step_result is None:
                    break
                else:
                    setattr(company_stats, field, step_result)
        db.session.add(company_stats)
        db.session.commit()


def get_or_init_company_stats(company):
    company_stats = CompanyStats.query.filter(
        CompanyStats.company_id == company.id
    ).one_or_none()
    if company_stats is None:
        company_stats = CompanyStats(
            company_id=company.id, company_creation_date=company.creation_time
        )
    return company_stats


def get_first_employee_invitation_date(company_id):
    return (
        db.session.query(db.func.min(Employment.creation_time))
        .filter(
            Employment.company_id == company_id, ~Employment.has_admin_rights
        )
        .first()
    )[0]


def get_first_mission_validation_by_admin_date(company_id):
    return (
        db.session.query(db.func.min(MissionValidation.creation_time))
        .join(Mission)
        .filter(
            Mission.company_id == company_id,
            MissionValidation.is_admin,
            MissionValidation.user_id != MissionValidation.submitter_id,
        )
        .first()
    )[0]


def get_first_active_criteria_date(company_id):
    return (
        db.session.query(db.func.min(CompanyCertification.attribution_date))
        .filter(
            CompanyCertification.company_id == company_id,
            CompanyCertification.be_active,
        )
        .first()
    )[0]


def get_first_certification_date(company_id):
    return (
        db.session.query(db.func.min(CompanyCertification.attribution_date))
        .filter(
            CompanyCertification.company_id == company_id,
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
        )
        .first()
    )[0]


STEPS = {
    "first_employee_invitation_date": get_first_employee_invitation_date,
    "first_mission_validation_by_admin_date": get_first_mission_validation_by_admin_date,
    "first_active_criteria_date": get_first_active_criteria_date,
    "first_certification_date": get_first_certification_date,
}
