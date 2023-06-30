from app.helpers.pdf import generate_pdf_from_template


def generate_company_certificate_pdf(company_certification):

    return generate_pdf_from_template(
        "company_certification_pdf.html",
        company_name=company_certification.company.usual_name,
        certificate_start_date=company_certification.attribution_date,
        certificate_end_date=company_certification.expiration_date,
    )
