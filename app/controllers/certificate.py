from datetime import date
from typing import NamedTuple

from flask import jsonify, request, abort
from flask_apispec import use_kwargs
from sqlalchemy.sql.functions import now
from webargs import fields

from app import app, db
from app.models import Company, CompanyCertification


class CertificationOutput(NamedTuple):
    siren: str
    siret: str
    certification_attribution_date: date
    certification_expiration_date: date


@app.route("/is_company_certified", methods=["POST"])
@use_kwargs(
    {"siren": fields.String(required=True)},
    apply=True,
)
def is_company_certified(siren):
    header_in_request = request.headers.get("X-MOBILIC-CERTIFICATION-KEY")
    if (
        not header_in_request
        or header_in_request != app.config["CERTIFICATION_API_KEY"]
    ):
        abort(401)

    certified_company_result = (
        db.session.query(
            Company.siren,
            Company.short_sirets,
            CompanyCertification.attribution_date,
            CompanyCertification.expiration_date,
        )
        .join(
            CompanyCertification, CompanyCertification.company_id == Company.id
        )
        .filter(
            Company.siren == siren,
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
            CompanyCertification.expiration_date > now(),
        )
        .all()
    )

    certified_companies = []
    for company in certified_company_result:
        company_dict = company._asdict()
        if len(company_dict["short_sirets"]) > 0:
            for siret in company_dict["short_sirets"]:
                certified_companies.append(
                    CertificationOutput(
                        siren=company_dict["siren"],
                        siret=company_dict["siren"] + f"{siret:05}",
                        certification_attribution_date=company_dict[
                            "attribution_date"
                        ],
                        certification_expiration_date=company_dict[
                            "expiration_date"
                        ],
                    )
                )
        else:
            certified_companies.append(
                CertificationOutput(
                    siren=company_dict["siren"],
                    certification_attribution_date=company_dict[
                        "attribution_date"
                    ],
                    certification_expiration_date=company_dict[
                        "expiration_date"
                    ],
                )
            )

    return jsonify([c._asdict() for c in certified_companies]), 200
