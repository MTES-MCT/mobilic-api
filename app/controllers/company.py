import graphene
from flask import send_file
from datetime import datetime, timedelta
from graphene.types.generic import GenericScalar
import requests
from sqlalchemy.orm import selectinload
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
import os

from webargs import fields
from marshmallow import Schema, validates_schema, ValidationError
from flask_apispec import use_kwargs, doc

from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.company import (
    SirenRegistrationStatus,
    get_siren_registration_status,
)
from app.domain.permissions import (
    is_employed_by_company_over_period,
    ConsultationScope,
    company_admin,
    AuthorizationError,
)
from app.helpers.authentication import (
    require_auth,
    AuthenticationError,
    AuthenticatedMutation,
)
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.authorization import (
    with_authorization_policy,
    current_user,
)
from app import siren_api_client, mailer
from app.helpers.errors import SirenAlreadySignedUpError
from app.helpers.graphene_types import graphene_enum_type
from app.helpers.integromat import call_integromat_webhook
from app.helpers.mail import MailingContactList
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
from app.services.update_companies_spreadsheet import (
    add_company_to_spreadsheet,
)


class CompanySignUp(AuthenticatedMutation):
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
    def mutate(cls, _, info, usual_name, siren, sirets):
        with atomic_transaction(commit_at_end=True):
            siren_api_info = None
            registration_status, _ = get_siren_registration_status(siren)

            if (
                registration_status != SirenRegistrationStatus.UNREGISTERED
                and not sirets
            ):
                raise SirenAlreadySignedUpError()
            try:
                siren_api_info = siren_api_client.get_siren_info(siren)
                (
                    legal_unit,
                    open_facilities,
                ) = siren_api_client.parse_legal_unit_and_open_facilities_info_from_dict(
                    siren_api_info
                )
            except Exception as e:
                app.logger.warning(
                    f"Could not add SIREN API info for company of SIREN {siren} : {e}"
                )

            require_kilometer_data = True
            require_support_activity = False
            if siren_api_info:
                # For déménagement companies disable kilometer data by default, and enable support activity
                if legal_unit.activity_code == "49.42Z":
                    require_kilometer_data = False
                    require_support_activity = True

            now = datetime.now()
            company = Company(
                usual_name=usual_name,
                siren=siren,
                short_sirets=[int(siret[9:]) for siret in sirets],
                siren_api_info=siren_api_info,
                allow_team_mode=True,
                require_kilometer_data=require_kilometer_data,
                require_support_activity=require_support_activity,
                require_mission_name=True,
            )
            db.session.add(company)
            db.session.flush()  # Early check for SIRET duplication

            admin_employment = Employment(
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

        if current_user.subscribed_mailing_lists:
            try:
                current_user.unsubscribe_from_contact_list(
                    MailingContactList.EMPLOYEES, remove=True
                )
                current_user.subscribe_to_contact_list(
                    MailingContactList.ADMINS
                )
            except Exception as e:
                app.logger.exception(e)

        if app.config["INTEGROMAT_COMPANY_SIGNUP_WEBHOOK"]:
            # Call Integromat for Trello card creation
            try:
                call_integromat_webhook(
                    company, legal_unit, open_facilities, current_user
                )
            except Exception as e:
                app.logger.warning(
                    f"Creation of Trello card for {company} failed with error : {e}"
                )

        if app.config["GOOGLE_PRIVATE_KEY"]:
            # Add new company to spreadsheet
            try:
                add_company_to_spreadsheet(company, current_user)
            except Exception as e:
                app.logger.warning(
                    f"Could not add {company} to spreadsheet because : {e}"
                )

        return CompanySignUp(company=company, employment=admin_employment)


class SirenInfo(graphene.ObjectType):
    registration_status = graphene_enum_type(SirenRegistrationStatus)(
        required=True
    )
    legal_unit = graphene.Field(GenericScalar)
    facilities = graphene.List(GenericScalar)


class NonPublicQuery(graphene.ObjectType):
    siren_info = graphene.Field(
        SirenInfo,
        siren=graphene.Int(required=True, description="SIREN de l'entreprise"),
        description="Interrogation de l'API SIRENE pour récupérer la liste des établissements associés à un SIREN",
    )

    def resolve_siren_info(self, info, siren):
        all_siren_info = siren_api_client.get_siren_info(siren)
        (
            legal_unit,
            open_facilities,
        ) = siren_api_client.parse_legal_unit_and_open_facilities_info_from_dict(
            all_siren_info
        )
        registration_status, registered_sirets = get_siren_registration_status(
            siren
        )

        facility_dicts = []
        for facility in open_facilities:
            d = facility._asdict()
            if (
                registration_status
                == SirenRegistrationStatus.PARTIALLY_REGISTERED
            ):
                d["registered"] = int(facility.siret[9:]) in registered_sirets
            facility_dicts.append(d)

        return SirenInfo(
            registration_status=registration_status,
            legal_unit=legal_unit._asdict(),
            facilities=facility_dicts,
        )


class EditCompanySettings(AuthenticatedMutation):
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
        require_mission_name = graphene.Boolean(
            required=False,
            description="Rend obligatoire ou non la saisie d'un nom pour une mission.",
        )

    Output = CompanyOutput

    @classmethod
    @with_authorization_policy(
        company_admin,
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
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, id: id,
        error_message="Forbidden access",
    )
    def resolve_company(self, info, id):
        matching_company = Company.query.get(id)
        return matching_company


@require_auth
def check_auth_and_get_users_list(company_ids, user_ids, min_date, max_date):
    if not set(company_ids) <= set(
        current_user.current_company_ids_with_admin_rights
    ):
        raise AuthorizationError("Forbidden access")

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

    all_users_work_days = []
    for user in users:
        all_users_work_days += group_user_events_by_day_with_limit(
            user,
            consultation_scope=scope,
            from_date=min_date,
            until_date=max_date,
            include_dismissed_or_empty_days=True,
        )[0]

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
        if data["max_date"] - data["min_date"] > timedelta(days=64):
            raise ValidationError(
                "The requested period should be less than 64 days"
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
                do_not_generate_if_empty=False,
            )
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
