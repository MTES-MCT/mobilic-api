import graphene
from flask import jsonify, send_file
from datetime import datetime, timedelta
from graphene.types.generic import GenericScalar
import requests
from sqlalchemy.orm import selectinload
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO

from webargs import fields
from marshmallow import Schema, validates_schema, ValidationError
from flask_apispec import use_kwargs, doc

from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.permissions import (
    belongs_to_company_at,
    ConsultationScope,
    company_admin_at,
)
from app.helpers.authentication import require_auth, AuthenticationError
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated,
    current_user,
)
from app import siren_api_client, mailer
from app.helpers.insee_tranche_effectifs import format_tranche_effectif
from app.helpers.tachograph import (
    generate_tachograph_parts,
    write_tachograph_archive,
    generate_tachograph_file_name,
)
from app.helpers.xls import send_work_days_as_excel
from app.models import Company, Employment, NafCode
from app.models.employment import (
    EmploymentRequestValidationStatus,
    EmploymentOutput,
)
from app import db, app


class CompanySignUp(graphene.Mutation):
    """
    Inscription d'une nouvelle entreprise.

    Retourne l'entreprise nouvellement créée
    """

    class Arguments:
        usual_name = graphene.String(
            required=True, description="Nom usuel de l'entreprise"
        )
        siren = graphene.Int(
            required=True, description="Numéro SIREN de l'entreprise"
        )
        sirets = graphene.List(
            graphene.String,
            required=False,
            description="Liste des SIRET des établissements associés à l'entreprise",
        )

    company = graphene.Field(CompanyOutput)
    employment = graphene.Field(EmploymentOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, usual_name, siren, sirets):
        with atomic_transaction(commit_at_end=True):
            siren_api_info = None
            try:
                siren_api_info = siren_api_client.get_siren_info(siren)
            except Exception as e:
                app.logger.warning(
                    f"Could not add SIREN API info for company of SIREN {siren} : {e}"
                )

            require_kilometer_data = True
            main_activity_code = ""
            if siren_api_info:
                formatted_main_activity = main_activity_code = siren_api_info[
                    "uniteLegale"
                ]["activitePrincipaleUniteLegale"]
                main_activity = (
                    NafCode.get_code(main_activity_code)
                    if main_activity_code
                    else None
                )
                if main_activity:
                    formatted_main_activity = (
                        f"{main_activity.code} {main_activity.label}"
                    )
                # For déménagement companies disable kilometer data by default
                if (
                    siren_api_info["uniteLegale"][
                        "nomenclatureActivitePrincipaleUniteLegale"
                    ]
                    == "NAFRev2"
                    and main_activity_code == "49.42Z"
                ):
                    require_kilometer_data = False

            now = datetime.now()
            company = Company(
                usual_name=usual_name,
                siren=siren,
                sirets=sirets,
                siren_api_info=siren_api_info,
                allow_team_mode=True,
                require_kilometer_data=require_kilometer_data,
            )
            db.session.add(company)
            db.session.flush()  # Early check for SIREN duplication

            admin_employment = Employment(
                is_primary=False if current_user.primary_company else True,
                user_id=current_user.id,
                company=company,
                start_date=now.date(),
                validation_time=now,
                validation_status=EmploymentRequestValidationStatus.APPROVED,
                has_admin_rights=True,
                reception_time=now,
                submitter_id=current_user.id,
            )
            db.session.add(admin_employment)

        app.logger.info(
            f"Signed up new company {company}",
            extra={
                "post_to_mattermost": True,
                "log_title": "New company signup",
                "emoji": ":tada:",
            },
        )

        try:
            mailer.send_company_creation_email(company, current_user)
        except Exception as e:
            app.logger.exception(e)

        if app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"]:
            # Call Integromat for Trello card creation
            try:
                first_establishment_info = (
                    siren_api_info["etablissements"][0]
                    if siren_api_info
                    else None
                )
                response = requests.post(
                    app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"],
                    data=dict(
                        name=company.name,
                        creation_time=company.creation_time,
                        submitter_name=current_user.display_name,
                        submitter_email=current_user.email,
                        siren=company.siren,
                        metabase_link=f"{app.config['METABASE_COMPANY_DASHBOARD_BASE_URL']}{company.id}",
                        location=f"{first_establishment_info.get('adresse', '')} {first_establishment_info.get('codePostal', '')}"
                        if first_establishment_info
                        else None,
                        activity_code=formatted_main_activity,
                        n_employees=format_tranche_effectif(
                            siren_api_info["uniteLegale"][
                                "trancheEffectifsUniteLegale"
                            ]
                        ),
                        n_employees_year=siren_api_info["uniteLegale"][
                            "anneeEffectifsUniteLegale"
                        ],
                    ),
                    timeout=3,
                )
                if not response.status_code == 200:
                    app.logger.warning(
                        f"Creation of Trello card for {company} failed with error : {response.text}"
                    )
            except Exception as e:
                app.logger.warning(
                    f"Creation of Trello card for {company} failed with error : {e}"
                )

        return CompanySignUp(company=company, employment=admin_employment)


class NonPublicQuery(graphene.ObjectType):
    siren_info = graphene.Field(
        GenericScalar,
        siren=graphene.Int(required=True, description="SIREN de l'entreprise"),
        description="Interrogation de l'API SIRENE pour récupérer la liste des établissements associés à un SIREN",
    )

    def resolve_siren_info(self, info, siren):
        all_siren_info = siren_api_client.get_siren_info(siren)
        return siren_api_client.extract_current_facilities_short_info(
            all_siren_info
        )


class EditCompanySettings(graphene.Mutation):
    class Arguments:
        company_id = graphene.Int(
            required=True, description="Identifiant de l'entreprise"
        )
        allow_team_mode = graphene.Boolean(
            required=False,
            description="Permet ou interdit la saisie en mode équipe",
        )
        require_kilometer_data = graphene.Boolean(
            required=False,
            description="Active ou désactive la saisie du kilométrage en début et fin de mission",
        )
        require_expenditures = graphene.Boolean(
            required=False,
            description="Active ou désactive la saisie des frais.",
        )
        require_support_activity = graphene.Boolean(
            required=False,
            description="Active ou désactive la prise en charge de l'accompagnement.",
        )

    Output = CompanyOutput

    @classmethod
    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda cls, _, info, **kwargs: Company.query.get(
            kwargs["company_id"]
        ),
        error_message="You need to be a company admin to be able to edit company settings",
    )
    def mutate(cls, _, info, company_id, **kwargs):
        with atomic_transaction(commit_at_end=True):
            company = Company.query.get(company_id)
            is_there_something_updated = False
            for field, value in kwargs.items():
                if value is not None:
                    current_field_value = getattr(company, field)
                    if current_field_value != value:
                        is_there_something_updated = True
                        setattr(company, field, value)

            if not is_there_something_updated:
                app.logger.warning("No setting was actually modified")
            db.session.add(company)

        return company


class Query(graphene.ObjectType):
    company = graphene.Field(
        CompanyOutput,
        id=graphene.Int(
            required=True, description="Identifiant de l'entreprise"
        ),
        description="Consultation des données de l'entreprise, avec notamment la liste de ses membres (et leurs enregistrements)",
    )

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info, id: id,
        error_message="Forbidden access",
    )
    def resolve_company(self, info, id):
        matching_company = Company.query.get(id)
        return matching_company


def check_auth_and_get_users_list(company_ids, user_ids, min_date, max_date):
    try:
        require_auth()()
    except AuthenticationError as e:
        return jsonify({"error": e.message}), 401

    if not set(company_ids) <= set(
        current_user.current_company_ids_with_admin_rights
    ):
        return jsonify({"error": "Forbidden access"}), 403

    companies = (
        Company.query.options(
            selectinload(Company.employments).selectinload(Employment.user)
        )
        .filter(Company.id.in_(company_ids))
        .all()
    )
    users = set(
        [
            user
            for company in companies
            for user in company.users_between(min_date, max_date)
        ]
    )
    if user_ids:
        users = [u for u in users if u.id in user_ids]
    return users


@app.route("/companies/download_activity_report", methods=["POST"])
@doc(description="Téléchargement du rapport d'activité au format Excel")
@use_kwargs(
    {
        "company_ids": fields.List(
            fields.Int(), required=True, validate=lambda l: len(l) > 0
        ),
        "user_ids": fields.List(fields.Int(), required=False),
        "min_date": fields.Date(required=False),
        "max_date": fields.Date(required=False),
    },
    apply=True,
)
def download_activity_report(
    company_ids, user_ids=None, min_date=None, max_date=None
):
    users = check_auth_and_get_users_list(
        company_ids, user_ids, min_date, max_date
    )
    scope = ConsultationScope(company_ids=company_ids)

    app.logger.info(f"Downloading activity report for {company_ids}")
    all_users_work_days = []
    for user in users:
        all_users_work_days += group_user_events_by_day(
            user,
            consultation_scope=scope,
            from_date=min_date,
            until_date=max_date,
            include_dismissed_or_empty_days=True,
        )

    return send_work_days_as_excel(
        all_users_work_days,
        companies=Company.query.filter(Company.id.in_(company_ids)).all(),
    )


class TachographGenerationScopeSchema(Schema):
    company_ids = fields.List(
        fields.Int(), required=True, validate=lambda l: len(l) > 0
    )
    user_ids = fields.List(fields.Int(), required=False)
    min_date = fields.Date(required=True)
    max_date = fields.Date(required=True)
    with_digital_signatures = fields.Boolean(required=False)

    @validates_schema
    def check_period_is_small_enough(self, data, **kwargs):
        if data["max_date"] - data["min_date"] > timedelta(days=60):
            raise ValidationError(
                "The requested period should be less than 60 days"
            )


@app.route("/companies/generate_tachograph_files", methods=["POST"])
@doc(
    description="Génération de fichiers C1B contenant les données d'activité des salariés"
)
@use_kwargs(TachographGenerationScopeSchema(), apply=True)
def download_tachograph_files(
    company_ids,
    min_date,
    max_date,
    with_digital_signatures=False,
    user_ids=None,
):
    users = check_auth_and_get_users_list(
        company_ids, user_ids, min_date, max_date
    )
    scope = ConsultationScope(company_ids=company_ids)

    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as f:
        for user in users:
            tachograph_data = generate_tachograph_parts(
                user,
                start_date=min_date,
                end_date=max_date,
                consultation_scope=scope,
                only_activities_validated_by_admin=False,
                with_signatures=with_digital_signatures,
                do_not_generate_if_empty=True,
            )
            if tachograph_data:
                f.writestr(
                    generate_tachograph_file_name(user),
                    write_tachograph_archive(tachograph_data),
                )

    archive.seek(0)
    return send_file(
        archive,
        mimetype="application/zip",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="fichiers_C1B.zip",
    )
