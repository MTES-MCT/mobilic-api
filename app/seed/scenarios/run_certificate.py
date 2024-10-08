from datetime import date

from app.domain.certificate_criteria import compute_company_certifications


def scenario_run_certificate():
    compute_company_certifications(date.today())
