from dataclasses import dataclass

from app.domain.company import get_start_last_certification_period

CERTIFICATION_DATE_FORMAT = "%Y/%m/%d"
PUBLIC_CERTIFICATION_DATE_FORMAT = "%d/%m/%Y"


@dataclass
class CertificationOutput:
    company_name: str
    siren: str
    certification_attribution_date: str
    certification_expiration_date: str
    siret: str = None


def compute_certified_companies_output(
    certified_company_result, date_format=CERTIFICATION_DATE_FORMAT
):
    certified_companies = []
    for company in certified_company_result:
        company_dict = company._asdict()
        date_beginning_certification = get_start_last_certification_period(
            company_dict["id"]
        )
        if (
            company_dict["short_sirets"]
            and len(company_dict["short_sirets"]) > 0
        ):
            for siret in company_dict["short_sirets"]:
                certified_companies.append(
                    CertificationOutput(
                        company_name=company_dict["usual_name"],
                        siren=company_dict["siren"],
                        siret=company_dict["siren"] + f"{siret:05}",
                        certification_attribution_date=date_beginning_certification.strftime(
                            date_format
                        ),
                        certification_expiration_date=company_dict[
                            "expiration_date"
                        ].strftime(date_format),
                    )
                )
        else:
            certified_companies.append(
                CertificationOutput(
                    company_name=company_dict["usual_name"],
                    siren=company_dict["siren"],
                    certification_attribution_date=date_beginning_certification.strftime(
                        date_format
                    ),
                    certification_expiration_date=company_dict[
                        "expiration_date"
                    ].strftime(date_format),
                )
            )
    return certified_companies
