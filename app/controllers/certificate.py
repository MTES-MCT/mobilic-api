import re

import graphene
from flask import jsonify, request, abort, send_file
from flask_apispec import use_kwargs
from webargs import fields

from app import app
from app.controllers.utils import Void, atomic_transaction
from app.data_access.certificate import (
    PUBLIC_CERTIFICATION_DATE_FORMAT,
    compute_certified_companies_output,
)
from app.domain.company import (
    change_company_certification_communication_pref,
    get_companies_by_siren,
    get_company_by_siret,
    find_companies_by_name,
    find_certified_companies_query,
    get_current_certificate,
)
from app.domain.permissions import companies_admin, company_admin
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.helpers.pdf.company_certificate import (
    generate_company_certificate_pdf,
)
from app.models import Company


@app.route("/companies/public_company_certification", methods=["POST"])
@use_kwargs(
    {"search_input": fields.String(required=True)},
    apply=True,
)
def public_company_certification(search_input):
    search_input = re.sub("[ .-]", "", search_input)
    found_companies = []
    if search_input.isdigit():
        if len(search_input) == 9:
            found_companies = get_companies_by_siren(search_input)
        elif len(search_input) == 14:
            found_company = get_company_by_siret(search_input)
            found_companies = [found_company] if found_company else []
    if len(found_companies) == 0:
        found_companies = find_companies_by_name(search_input)

    certified_company_result = (
        find_certified_companies_query()
        .filter(Company.id.in_([c.id for c in found_companies]))
        .all()
    )
    certified_companies = compute_certified_companies_output(
        certified_company_result, date_format=PUBLIC_CERTIFICATION_DATE_FORMAT
    )

    return jsonify([c for c in certified_companies]), 200


@app.route("/companies/is_company_certified", methods=["POST"])
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
        find_certified_companies_query().filter(Company.siren == siren).all()
    )
    certified_companies = compute_certified_companies_output(
        certified_company_result
    )

    return jsonify([c for c in certified_companies]), 200


class EditCompanyCommunicationSetting(AuthenticatedMutation):
    class Arguments:
        company_ids = graphene.List(
            graphene.Int,
            required=True,
            description="Identifiants des entreprises.",
        )
        accept_certification_communication = graphene.Boolean(
            required=True,
            description="True si la communication sur la certification est acceptée",
        )

    Output = Void

    @classmethod
    @with_authorization_policy(
        companies_admin,
        get_target_from_args=lambda cls, _, info, **kwargs: kwargs[
            "company_ids"
        ],
        error_message="You need to be a company admin to be able to edit company communication settings",
    )
    def mutate(cls, _, info, company_ids, accept_certification_communication):
        with atomic_transaction(commit_at_end=True):
            change_company_certification_communication_pref(
                company_ids, accept_certification_communication
            )

        return Void(success=True)


@app.route("/companies/download_certificate", methods=["POST"])
@use_kwargs({"company_id": fields.Int(required=True)}, apply=True)
@with_authorization_policy(
    company_admin,
    get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
)
def download_certificate(company_id):

    company_certification = get_current_certificate(company_id)

    pdf = generate_company_certificate_pdf(company_certification)

    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="Certificat_Mobilic.pdf",
    )
