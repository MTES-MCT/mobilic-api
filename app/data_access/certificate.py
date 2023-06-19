from dataclasses import dataclass

CERTIFICATION_DATE_FORMAT = "%Y/%m/%d"
PUBLIC_CERTIFICATION_DATE_FORMAT = "%d/%m/%Y"


@dataclass
class CertificationOutput:
    company_name: str
    company_subscription_date: str
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
        if (
            company_dict["short_sirets"]
            and len(company_dict["short_sirets"]) > 0
        ):
            for siret in company_dict["short_sirets"]:
                certified_companies.append(
                    CertificationOutput(
                        company_name=company_dict["usual_name"],
                        company_subscription_date=company_dict[
                            "creation_time"
                        ].strftime(date_format)
                        if company_dict["creation_time"]
                        else None,
                        siren=company_dict["siren"],
                        siret=company_dict["siren"] + f"{siret:05}",
                        certification_attribution_date=company_dict[
                            "attribution_date"
                        ].strftime(date_format),
                        certification_expiration_date=company_dict[
                            "expiration_date"
                        ].strftime(date_format),
                    )
                )
        else:
            certified_companies.append(
                CertificationOutput(
                    company_name=company_dict["usual_name"],
                    company_subscription_date=company_dict[
                        "creation_time"
                    ].strftime(date_format)
                    if company_dict["creation_time"]
                    else None,
                    siren=company_dict["siren"],
                    certification_attribution_date=company_dict[
                        "attribution_date"
                    ].strftime(date_format),
                    certification_expiration_date=company_dict[
                        "expiration_date"
                    ].strftime(date_format),
                )
            )
    return certified_companies
