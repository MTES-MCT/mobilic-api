from datetime import datetime

import graphene
from flask import send_file
from flask_apispec import use_kwargs, doc
from graphene.types.generic import GenericScalar
from sqlalchemy.orm import selectinload
from webargs import fields

from app import db, app
from app import siren_api_client, mailer
from app.controllers.user import TachographBaseOptionsSchema
from app.controllers.utils import atomic_transaction
from app.data_access.company import CompanyOutput
from app.domain.company import (
    SirenRegistrationStatus,
    get_siren_registration_status,
    link_company_to_software,
)
from app.domain.permissions import (
    is_employed_by_company_over_period,
    ConsultationScope,
    company_admin,
    AuthorizationError,
)
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.api_key_authentication import (
    ProtectedMutation,
    check_protected_client_id,
)
from app.helpers.authentication import (
    require_auth,
    AuthenticatedMutation,
)
from app.helpers.authorization import (
    with_authorization_policy,
    current_user,
    with_protected_authorization_policy,
)
from app.helpers.errors import (
    SirenAlreadySignedUpError,
)
from app.helpers.graphene_types import graphene_enum_type
from app.helpers.mail import MailingContactList
from app.helpers.tachograph import (
    get_tachograph_archive_company,
)
from app.helpers.xls.companies import send_work_days_as_excel
from app.models import Company, Employment
from app.models.employment import (
    EmploymentRequestValidationStatus,
    EmploymentOutput,
)
from app.services.update_companies_spreadsheet import (
    add_company_to_spreadsheet,
)


class CompanySignUpOutput(graphene.ObjectType):
    company = graphene.Field(CompanyOutput)
    employment = graphene.Field(EmploymentOutput)


class CompanySoftwareRegistration(ProtectedMutation):
    """
    Enregistrement d'une nouvelle liaison entre un logiciel tiers et une entreprise.
    Si besoin, l'entreprise va être créée.
    """

    class Arguments:
        client_id = graphene.Int(
            required=True, description="Client id du logiciel"
        )
        usual_name = graphene.String(
            required=True, description="Nom usuel de l'entreprise"
        )
        siren = graphene.String(
            required=True, description="Numéro SIREN de l'entreprise"
        )
        siret = graphene.String(
            required=False, description="Numéro de Siret de l'établissement"
        )

    Output = CompanyOutput

    @classmethod
    @with_protected_authorization_policy(
        authorization_rule=check_protected_client_id,
        get_target_from_args=lambda *args, **kwargs: kwargs["client_id"],
        error_message="You do not have access to the provided client id",
    )
    def mutate(cls, _, info, client_id, usual_name, siren, siret=None):
        with atomic_transaction(commit_at_end=True):
            company = create_company_by_third_party(usual_name, siren, siret)
            link_company_to_software(company.id, client_id)
        return company


class CompanySignUp(AuthenticatedMutation):
    """
    Inscription d'une nouvelle entreprise.

    Retourne l'entreprise nouvellement créée
    """

    class Arguments:
        usual_name = graphene.String(
            required=True, description="Nom usuel de l'entreprise"
        )
        siren = graphene.String(
            required=True, description="Numéro SIREN de l'entreprise"
        )

    Output = CompanySignUpOutput

    @classmethod
    def mutate(cls, _, info, usual_name, siren):
        return sign_up_company(usual_name, siren)


class CompanySiret(graphene.InputObjectType):
    siret = graphene.String()
    usual_name = graphene.String()


class CompaniesSignUp(AuthenticatedMutation):
    """
    Inscription de plusieurs nouvelles entreprises distinctes

    Retourne la liste des entreprises créées
    """

    class Arguments:
        siren = graphene.String(
            required=True, description="Numéro SIREN des entreprises"
        )
        companies = graphene.List(
            CompanySiret,
            required=True,
            description="Liste des informations relatives aux entreprises à créer",
        )

    Output = graphene.List(CompanySignUpOutput)

    @classmethod
    def mutate(cls, _, info, siren, companies):
        return sign_up_companies(siren, companies)


def sign_up_companies(siren, companies):
    created_companies = [
        sign_up_company(
            company.get("usual_name"),
            siren,
            [company.get("siret")],
            send_email=len(companies) == 1,
        )
        for company in companies
    ]

    try:
        if len(companies) > 1:
            mailer.send_companies_creation_email(
                companies, siren, current_user
            )
    except Exception as e:
        app.logger.exception(e)

    return created_companies


def create_company_by_third_party(usual_name, siren, siret):
    created_company = store_company(
        siren, [siret] if siret else [], usual_name
    )
    return created_company


def sign_up_company(usual_name, siren, sirets=[], send_email=True):
    with atomic_transaction(commit_at_end=True):
        company = store_company(siren, sirets, usual_name)

        now = datetime.now()
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

    if send_email:
        try:
            mailer.send_company_creation_email(company, current_user)
        except Exception as e:
            app.logger.exception(e)

    if current_user.subscribed_mailing_lists:
        try:
            current_user.unsubscribe_from_contact_list(
                MailingContactList.EMPLOYEES, remove=True
            )
            current_user.subscribe_to_contact_list(MailingContactList.ADMINS)
        except Exception as e:
            app.logger.exception(e)

    if app.config["GOOGLE_PRIVATE_KEY"]:
        # Add new company to spreadsheet
        try:
            add_company_to_spreadsheet(company, current_user)
        except Exception as e:
            app.logger.warning(
                f"Could not add {company} to spreadsheet because : {e}"
            )

    return CompanySignUpOutput(company=company, employment=admin_employment)


def store_company(siren, sirets, usual_name):
    registration_status, _ = get_siren_registration_status(siren)

    if (
        registration_status != SirenRegistrationStatus.UNREGISTERED
        and not sirets
    ):
        raise SirenAlreadySignedUpError()
    siren_api_info = None
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
    company = Company(
        usual_name=usual_name,
        siren=siren,
        short_sirets=[int(siret[9:]) for siret in sirets],
        siren_api_info=siren_api_info,
        allow_team_mode=True,
        allow_transfers=False,
        require_kilometer_data=require_kilometer_data,
        require_support_activity=require_support_activity,
        require_mission_name=True,
    )
    db.session.add(company)
    db.session.flush()  # Early check for SIRET duplication
    return company


class SirenInfo(graphene.ObjectType):
    registration_status = graphene_enum_type(SirenRegistrationStatus)(
        required=True
    )
    legal_unit = graphene.Field(GenericScalar)
    facilities = graphene.List(GenericScalar)


class NonPublicQuery(graphene.ObjectType):
    siren_info = graphene.Field(
        SirenInfo,
        siren=graphene.String(
            required=True, description="SIREN de l'entreprise"
        ),
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
        allow_transfers = graphene.Boolean(
            required=False,
            description="Active ou désactive la possibilité d'enregistrer des temps de liaison",
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
        "one_file_by_employee": fields.Boolean(required=False),
    },
    apply=True,
)
def download_activity_report(
    company_ids,
    user_ids=None,
    min_date=None,
    max_date=None,
    one_file_by_employee=False,
):
    users = check_auth_and_get_users_list(
        company_ids, user_ids, min_date, max_date
    )
    scope = ConsultationScope(company_ids=company_ids)

    if one_file_by_employee:
        user_wdays_batches = []
        for user in users:
            user_wdays_batches += [
                (
                    user,
                    group_user_events_by_day_with_limit(
                        user,
                        consultation_scope=scope,
                        from_date=min_date,
                        until_date=max_date,
                        include_dismissed_or_empty_days=True,
                    )[0],
                )
            ]
    else:
        all_users_work_days = []
        for user in users:
            all_users_work_days += group_user_events_by_day_with_limit(
                user,
                consultation_scope=scope,
                from_date=min_date,
                until_date=max_date,
                include_dismissed_or_empty_days=True,
            )[0]
        user_wdays_batches = [(None, all_users_work_days)]

    return send_work_days_as_excel(
        user_wdays_batches=user_wdays_batches,
        companies=Company.query.filter(Company.id.in_(company_ids)).all(),
        min_date=min_date,
        max_date=max_date,
    )


class TachographGenerationScopeSchema(TachographBaseOptionsSchema):
    company_ids = fields.List(
        fields.Int(), required=True, validate=lambda l: len(l) > 0
    )
    user_ids = fields.List(fields.Int(), required=False)


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

    archive = get_tachograph_archive_company(
        users=users,
        min_date=min_date,
        max_date=max_date,
        scope=scope,
        with_signatures=with_digital_signatures,
    )
    return send_file(
        archive,
        mimetype="application/zip",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="fichiers_C1B.zip",
    )
