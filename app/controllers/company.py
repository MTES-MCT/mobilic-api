from datetime import datetime

import graphene
from flask import send_file, jsonify, make_response
from flask_apispec import use_kwargs, doc
from graphene.types.generic import GenericScalar
from sqlalchemy.orm import selectinload
from webargs import fields

from app import db, app
from app import siren_api_client, mailer
from app.controllers.user import TachographBaseOptionsSchema
from app.controllers.utils import atomic_transaction, Void
from app.data_access.company import CompanyOutput
from app.data_access.employment import EmploymentOutput
from app.domain.company import (
    SirenRegistrationStatus,
    get_siren_registration_status,
    link_company_to_software,
    apply_business_type_to_company_employees,
)
from app.domain.permissions import (
    is_employed_by_company_over_period,
    ConsultationScope,
    company_admin,
    AuthorizationError,
)
from app.helpers.api_key_authentication import (
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
    check_company_ids_against_scope,
)
from app.helpers.errors import (
    SirenAlreadySignedUpError,
    InvalidParamsError,
    CompanyCeasedActivityError,
)
from app.helpers.graphene_types import graphene_enum_type, Email
from app.helpers.mail import MailingContactList
from app.helpers.siren import (
    has_ceased_activity_from_siren_info,
    validate_siren,
)
from app.helpers.tachograph import (
    get_tachograph_archive_company,
)
from app.models import Company, Employment, Business, UserAgreement
from app.models.business import BusinessType
from app.models.employment import (
    EmploymentRequestValidationStatus,
)
from app.helpers.brevo import (
    brevo,
    CreateContactData,
    CreateCompanyData,
    LinkCompanyContactData,
    BrevoRequestError,
)
import sentry_sdk

from app.services.exports import export_activity_report

from app.models.user import User


def _validate_company_params(usual_name, siren, siret=None, nb_workers=None):
    """Validate company registration parameters"""
    if not usual_name or not usual_name.strip():
        raise InvalidParamsError("Company usual name is required")

    siren_error = validate_siren(siren)
    if siren_error:
        raise InvalidParamsError(siren_error)

    if siret:
        if len(siret) != 14 or not siret.isdigit():
            raise InvalidParamsError("SIRET must be exactly 14 digits")
        if not siret.startswith(siren):
            raise InvalidParamsError("SIRET must start with the company SIREN")

    if nb_workers is not None and nb_workers <= 0:
        raise InvalidParamsError("Number of workers must be greater than 0")


class CompanySignUpOutput(graphene.ObjectType):
    company = graphene.Field(CompanyOutput)
    employment = graphene.Field(EmploymentOutput)


class CompanySoftwareRegistration(graphene.Mutation):
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
            required=True,
            description="Numéro SIREN de l'entreprise (9 caractères numériques)",
        )
        siret = graphene.String(
            required=False, description="Numéro de Siret de l'établissement"
        )
        nb_workers = graphene.Int(
            required=True,
            description="Nombre de salarié de l'entreprise/établissement",
        )

    Output = CompanyOutput

    @classmethod
    @with_protected_authorization_policy(
        authorization_rule=check_protected_client_id,
        get_target_from_args=lambda *args, **kwargs: kwargs["client_id"],
        error_message="You do not have access to the provided client id",
    )
    def mutate(
        cls, _, info, client_id, usual_name, siren, siret=None, nb_workers=None
    ):
        _validate_company_params(usual_name, siren, siret, nb_workers)

        with atomic_transaction(commit_at_end=True):
            company = create_company_by_third_party(
                usual_name, siren, siret, nb_workers
            )
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
        phone_number = graphene.String(
            required=False,
            description="Numéro de téléphone de l'entreprise",
        )
        business_type = graphene.String(
            required=False,
            description="Type d'activité de transport effectué par l'entreprise",
        )
        nb_workers = graphene.Int(
            required=False,
            description="Nombre de chauffeurs et/ou travailleurs mobiles",
        )

    Output = CompanySignUpOutput

    @classmethod
    def mutate(
        cls,
        _,
        info,
        usual_name,
        siren,
        business_type="",
        phone_number="",
        nb_workers=None,
    ):
        _validate_company_params(
            usual_name, siren, siret=None, nb_workers=nb_workers
        )

        return sign_up_company(
            usual_name, siren, business_type, phone_number, nb_workers
        )


class CompanySiret(graphene.InputObjectType):
    siret = graphene.String()
    usual_name = graphene.String()
    phone_number = graphene.String(
        required=False,
        description="Numéro de téléphone de l'entreprise",
    )
    business_type = graphene.String(
        required=False,
        description="Type d'activité de transport de l'entreprise",
    )
    nb_workers = graphene.Int(
        required=False,
        description="Nombre de chauffeurs et/ou travailleurs mobiles",
    )


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
        if not companies or len(companies) == 0:
            raise InvalidParamsError("Companies list cannot be empty")

        for idx, company in enumerate(companies):
            try:
                _validate_company_params(
                    usual_name=company.get("usual_name"),
                    siren=siren,
                    siret=company.get("siret"),
                    nb_workers=company.get("nb_workers"),
                )
            except InvalidParamsError as e:
                raise InvalidParamsError(f"Company {idx + 1}: {str(e)}")

        return sign_up_companies(siren, companies)


def sign_up_companies(siren, companies):
    created_companies = []
    for company in companies:
        try:
            created_company = sign_up_company(
                usual_name=company.get("usual_name"),
                siren=siren,
                phone_number=company.get("phone_number", ""),
                business_type=company.get("business_type", ""),
                nb_workers=company.get("nb_workers", None),
                sirets=[company.get("siret")],
                send_email=len(companies) == 1,
            )
            created_companies.append(created_company)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            continue

    try:
        if len(companies) > 1:
            mailer.send_companies_creation_email(
                companies, siren, current_user
            )
    except Exception as e:
        app.logger.exception(e)

    return created_companies


def create_company_by_third_party(usual_name, siren, siret, nb_workers):
    created_company = store_company(
        siren, [siret] if siret else [], usual_name, nb_workers=nb_workers
    )
    return created_company


def sign_up_company(
    usual_name,
    siren,
    business_type="",
    phone_number="",
    nb_workers=None,
    sirets=[],
    send_email=True,
):
    business = None
    if business_type:
        business = Business.query.filter(
            Business.business_type == BusinessType[business_type].value
        ).one_or_none()

    with atomic_transaction(commit_at_end=True):
        company = store_company(
            siren, sirets, usual_name, business, phone_number, nb_workers
        )

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
            business=business,
        )
        db.session.add(admin_employment)

    try:
        contact_data = CreateContactData(
            email=current_user.email,
            admin_first_name=current_user.first_name,
            admin_last_name=current_user.last_name,
            company_name=company.usual_name,
            siren=int(company.siren),
            phone_number=(
                current_user.phone_number
                if current_user.phone_number
                else None
            ),
        )

        contact_id = brevo.create_contact(contact_data)

        if contact_id is None:
            app.logger.warning(
                "Brevo API key not configured, skipping CRM sync"
            )
        else:
            company_id = brevo.create_company(
                CreateCompanyData(
                    company_name=company.usual_name,
                    siren=int(company.siren),
                    phone_number=(
                        company.phone_number if company.phone_number else None
                    ),
                )
            )

            if company_id is not None:
                brevo.link_company_and_contact(
                    LinkCompanyContactData(
                        company_id=company_id,
                        contact_id=contact_id,
                    )
                )
    except Exception as e:
        sentry_sdk.capture_exception(e)

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

    return CompanySignUpOutput(company=company, employment=admin_employment)


def store_company(
    siren, sirets, usual_name, business=None, phone_number="", nb_workers=None
):
    registration_status, _ = get_siren_registration_status(siren)

    if (
        registration_status != SirenRegistrationStatus.UNREGISTERED
        and not sirets
    ):
        raise SirenAlreadySignedUpError()

    if (
        registration_status == SirenRegistrationStatus.FULLY_REGISTERED
        and sirets
    ):
        raise SirenAlreadySignedUpError(
            "Company already registered globally for this SIREN (representing all establishments). Cannot create SIRET-specific establishments."
        )
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
        if has_ceased_activity_from_siren_info(siren_api_info):
            raise CompanyCeasedActivityError()

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
        phone_number=phone_number,
        business=business,
        number_workers=nb_workers,
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
        allow_other_task = graphene.Boolean(
            required=False,
            description="Indique si l'entreprise permet de saisir des activités de type 'Autre tâche'",
        )
        other_task_label = graphene.String(
            required=False,
            description="Sous-titre de l'activité de type 'Autre tâche'",
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
            updated_fields = []

            for field, value in kwargs.items():
                if value is not None:
                    current_field_value = getattr(company, field)
                    if current_field_value != value:
                        is_there_something_updated = True
                        setattr(company, field, value)
                        updated_fields.append(field)

            if not is_there_something_updated:
                app.logger.warning("No setting was actually modified")

            app.logger.info(f"Updated fields: {', '.join(updated_fields)}")

            db.session.add(company)

        return company


class UpdateCompanyDetails(AuthenticatedMutation):
    class Arguments:
        company_id = graphene.Int(
            required=True, description="Identifiant de l'entreprise"
        )
        new_name = graphene.String(
            required=False, description="Nouveau nom de l'entreprise"
        )
        new_phone_number = graphene.String(
            required=False,
            description="Nouveau numéro de téléphone de l'entreprise",
        )
        new_business_type = graphene.String(
            required=False,
            description="Nouveau type d'activité de transport de l'entreprise.",
        )
        new_nb_workers = graphene.Int(
            required=False,
            description="Nouveau nombre d'employés de l'entreprise.",
        )
        apply_business_type_to_employees = graphene.Boolean(
            required=False,
            description="Indique si l'on souhaite appliquer le nouveau type d'activité à tous les salariés de l'entreprise.",
        )

    Output = CompanyOutput

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda cls, _, info, **kwargs: Company.query.get(
            kwargs["company_id"]
        ),
        error_message="You need to be a company admin to be able to edit company name and/or phone number",
    )
    def mutate(
        cls,
        _,
        info,
        company_id,
        new_name="",
        new_phone_number="",
        new_business_type="",
        new_nb_workers=None,
        apply_business_type_to_employees=False,
    ):
        with atomic_transaction(commit_at_end=True):
            company = Company.query.get(company_id)

            current_name = company.usual_name
            current_phone_number = company.phone_number
            current_nb_workers = company.number_workers
            if current_name != new_name and new_name != "":
                company.usual_name = new_name
                app.logger.info(
                    f"Company name changed from {current_name} to {new_name}"
                )
            if (
                current_phone_number != new_phone_number
                and new_phone_number != ""
            ):
                company.phone_number = new_phone_number
                app.logger.info(
                    f"Company phone number changed from {current_phone_number} to {new_phone_number}"
                )
            if (
                current_nb_workers != new_nb_workers
                and new_nb_workers is not None
            ):
                if new_nb_workers <= 0:
                    raise InvalidParamsError(
                        "Number of workers must be greater than 0"
                    )
                company.number_workers = new_nb_workers
                app.logger.info(
                    f"Company number of workers changed from {current_nb_workers} to {new_nb_workers}"
                )
            if new_business_type != "":
                new_business = Business.query.filter(
                    Business.business_type
                    == BusinessType[new_business_type].value
                ).one_or_none()
                if new_business is None:
                    raise InvalidParamsError(
                        f"Business type {new_business_type} not found"
                    )
                if new_business.id != company.business_id:
                    company.business = new_business
                    app.logger.info(
                        f"Company business type changed to {new_business}"
                    )
                    if apply_business_type_to_employees:
                        apply_business_type_to_company_employees(
                            company, new_business
                        )
                        app.logger.info(
                            f"New business type applied to all employees"
                        )

            db.session.add(company)

        return company


class InviteCompanies(AuthenticatedMutation):
    class Arguments:
        company_id = graphene.Int(
            required=True,
            description="Identifiant de l'entreprise invitant d'autres entreprises.",
        )
        emails = graphene.Argument(
            graphene.List(Email),
            required=True,
            description="Liste d'emails à inviter.",
        )

    Output = Void

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda cls, _, info, **kwargs: Company.query.get(
            kwargs["company_id"]
        ),
        error_message="You need to be a company admin to invite other companies",
    )
    def mutate(cls, _, info, company_id, emails):
        try:
            company = Company.query.get(company_id)
            for email in emails:
                mailer.send_email_discover_mobilic(
                    from_company=company, to_email=email
                )
            return Void(success=True)

        except Exception as e:
            app.logger.exception(e)
            raise e


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

    check_company_ids_against_scope(company_ids)
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
@doc(
    description="Demande d'envoi du rapport d'activité au format Excel par email"
)
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

    export_activity_report(
        exporter=current_user,
        company_ids=company_ids,
        users=users,
        min_date=min_date,
        max_date=max_date,
        one_file_by_employee=one_file_by_employee,
    )

    return jsonify({"result": "ok"}), 200


@app.route("/users/download_full_data_when_CGU_refused", methods=["POST"])
@doc(
    description="Demande d'envoi du rapport d'activité complet en cas de refus des CGU"
)
@use_kwargs(
    {"user_id": fields.Int(required=True)},
    apply=True,
)
def download_full_data_report(user_id):
    try:
        user = User.query.get(user_id)
        company_ids = set(
            employment.company_id for employment in user.employments
        )

        for company_id in company_ids:
            company = (
                Company.query.options(
                    selectinload(Company.employments).selectinload(
                        Employment.user
                    )
                )
                .filter(Company.id == company_id)
                .one_or_none()
            )
            if company is None:
                continue

            users = set()
            is_user_admin = user.has_admin_rights(company_id)
            if is_user_admin:
                users.update(company.users_between(start=None, end=None))
            else:
                users.add(user)

            min_date = min(user.creation_time.date() for user in users)
            max_date = datetime.now().date()

            if is_user_admin:
                file_name = f"{company.usual_name}_rapport_activités_{min_date.strftime('%d/%m/%Y')} au {max_date.strftime('%d/%m/%Y')}"
            else:
                file_name = f"Relevé d'heures de {user.display_name} - {min_date.strftime('%d/%m/%Y')} au {max_date.strftime('%d/%m/%Y')} - {company.usual_name}"

            export_activity_report(
                exporter=user,
                company_ids=[company_id],
                users=users,
                min_date=min_date,
                max_date=max_date,
                one_file_by_employee=False,
                file_name=file_name,
                is_admin=is_user_admin,
            )

        UserAgreement.set_transferred_data_date(user.id)

        response = make_response(jsonify({"result": "ok"}), 200)
        response.headers["Content-Type"] = "application/json"
        return response

    except Exception as e:
        response = make_response(jsonify({"error": str(e)}), 500)
        response.headers["Content-Type"] = "application/json"
        return response


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
    employee_version=False,
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
        employee_version=employee_version,
    )
    return send_file(
        archive,
        mimetype="application/zip",
        as_attachment=True,
        download_name="fichiers_C1B.zip",
    )
