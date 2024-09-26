from mailjet_rest import Client
from contextlib import contextmanager
import jwt
from enum import Enum
from cached_property import cached_property
from flask import render_template
from datetime import datetime
from markupsafe import Markup

from app import app
from app.helpers.errors import MobilicError
from app.helpers.time import to_fr_tz
from app.helpers.mail_type import EmailType
from config import MOBILIC_ENV

CONTACT_ADDRESS = "contact@mobilic.beta.gouv.fr"
SENDER_ADDRESS = "nepasrepondre@mobilic.beta.gouv.fr"
SENDER_NAME = "Mobilic"


MAILJET_API_REQUEST_TIMEOUT = 10


class MailingContactList(str, Enum):
    EMPLOYEES = "employees"
    ADMINS = "admins"
    CONTROLLERS = "controllers"
    SOFTWARES = "softwares"


MAILJET_CONTACT_LIST_IDS = {
    MailingContactList.EMPLOYEES: 58466
    if app.config["ENABLE_NEWSLETTER_SUBSCRIPTION"]
    else 58470,
    MailingContactList.ADMINS: 58293
    if app.config["ENABLE_NEWSLETTER_SUBSCRIPTION"]
    else 58470,
    MailingContactList.CONTROLLERS: 58467
    if app.config["ENABLE_NEWSLETTER_SUBSCRIPTION"]
    else 58470,
    MailingContactList.SOFTWARES: 58468
    if app.config["ENABLE_NEWSLETTER_SUBSCRIPTION"]
    else 58470,
}


class MailjetSubscriptionStatus(str, Enum):
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    NONE = "none"


# The following values are defined by Mailjet, don't change them !
class MailjetSubscriptionActions(str, Enum):
    SUBSCRIBE = "addforce"
    UNSUBSCRIBE = "unsub"
    REMOVE = "remove"


class MailjetSuccess:
    def __init__(self, message_id):
        self.message_id = message_id


class MailjetError(MobilicError):
    code = "MAILJET_ERROR"


class InvalidEmailAddressError(MailjetError):
    code = "INVALID_EMAIL_ADDRESS"


class SubscriptionRequestError(MailjetError):
    code = "SUBSCRIPTION_REQUEST_ERROR"


class MailjetMessage:
    def __init__(
        self,
        email_type,
        add_sender=True,
        subject=None,
        recipient=None,
        user=None,
        employment=None,
        html=None,
        template_id=None,
        template_vars=None,
        attachment=None,
    ):
        if not html and not template_id:
            raise ValueError(
                "Either the html body or a template id should be provided when sending a mail request to Mailjet"
            )
        self.email_type = email_type
        self.recipient = recipient
        self.add_sender = add_sender
        self.subject = subject
        self.user = user
        self.employment = employment
        self.html = html
        self.template_id = template_id
        self.template_vars = template_vars
        self.response = None
        self.attachment = attachment

    @cached_property
    def actual_recipient(self):
        return self.user.email if self.user else self.recipient

    @cached_property
    def payload(self):
        if self.html:
            payload = {"HTMLPart": self.html}
        else:
            payload = {
                "TemplateID": self.template_id,
                "TemplateLanguage": True,
                "Variables": self.template_vars or {},
            }

        payload["To"] = [{"Email": self.actual_recipient}]
        if self.add_sender:
            payload["From"] = {"Email": SENDER_ADDRESS, "Name": SENDER_NAME}
        if self.subject:
            payload["Subject"] = self.subject
        if self.attachment:
            payload["Attachments"] = [self.attachment]

        return payload

    def parse_response(self, response):
        try:
            if response["Status"] == "success":
                self.response = MailjetSuccess(response["To"][0]["MessageID"])
            else:
                errors = response["Errors"]
                if any([e["ErrorCode"] == "mj-0013" for e in errors]):
                    self.response = InvalidEmailAddressError(
                        f"Mailjet could not send email to invalid address : {self.actual_recipient}"
                    )
                else:
                    self.response = MailjetError(
                        f"Mailjet could not send this email because : {response}"
                    )
        except:
            self.response = MailjetError(
                f"Mailjet could not send this email because : {response}"
            )

    @cached_property
    def email_sent_dict(self):
        if isinstance(self.response, MailjetSuccess):
            return dict(
                mailjet_id=self.response.message_id,
                address=self.actual_recipient,
                user_id=self.user.id if self.user else None,
                type=self.email_type,
                employment_id=self.employment.id if self.employment else None,
            )
        return None


# Mailjet is used as the email solution : what follows is the wrapper of their API, whose doc is here : https://github.com/mailjet/mailjet-apiv3-python
class Mailer:
    def __init__(self):
        self.mailjet = Client(
            auth=(
                app.config["MAILJET_API_KEY"],
                app.config["MAILJET_API_SECRET"],
            ),
            version="v3.1",
        )

    def send_batch(
        self,
        messages,
        _disable_commit=False,
        _apply_whitelist_if_not_prod=False,
    ):
        from app.models import Email
        from app import db

        if app.config["DISABLE_EMAIL"]:
            app.logger.info(
                f"Email not sent because DISABLE_EMAIL is set to true"
            )
            return
        if _apply_whitelist_if_not_prod and MOBILIC_ENV != "prod":
            app.logger.info("Emails will be filtered out based on whitelist")
            messages = [
                m
                for m in messages
                if m.actual_recipient in app.config["BATCH_EMAIL_WHITELIST"]
            ]
        messages = [
            m
            for m in messages
            if m.actual_recipient not in app.config["USERS_BLACKLIST"]
        ]
        if len(messages) == 0:
            return

        response = self.mailjet.send.create(
            data={"Messages": [m.payload for m in messages]},
            timeout=MAILJET_API_REQUEST_TIMEOUT,
        )
        try:
            all_message_responses = response.json()["Messages"]
            for index, message_response in enumerate(all_message_responses):
                messages[index].parse_response(message_response)
        except:
            raise MailjetError(
                f"Request to Mailjet API failed with error : {response.json()}"
            )

        emails_sent = []
        for message in messages:
            if message.email_sent_dict:
                emails_sent.append(message.email_sent_dict)

        if emails_sent:
            if len(messages) > 1:
                db.session.bulk_insert_mappings(Email, emails_sent)
            else:
                for email_sent in emails_sent:
                    db.session.add(Email(**email_sent))
            db.session.commit() if not _disable_commit else db.session.flush()

    def _send_single(
        self,
        message,
        _disable_commit=False,
        _apply_whitelist_if_not_prod=False,
    ):
        self.send_batch(
            [message],
            _disable_commit=_disable_commit,
            _apply_whitelist_if_not_prod=_apply_whitelist_if_not_prod,
        )
        if isinstance(message.response, MailjetError):
            raise message.response

    @staticmethod
    def _create_message_from_mailjet_template(
        template_id,
        type_,
        subject=None,
        recipient=None,
        user=None,
        _disable_commit=False,
        **kwargs,
    ):
        return MailjetMessage(
            template_id=template_id,
            template_vars=kwargs,
            subject=subject,
            recipient=recipient,
            user=user,
            email_type=type_,
            add_sender=False,
            employment=kwargs.get("employment"),
        )

    @staticmethod
    def _create_message_from_flask_template(
        template,
        type_,
        subject,
        recipient=None,
        user=None,
        _disable_commit=False,
        attachment=None,
        **kwargs,
    ):
        html = render_template(template, **kwargs)
        return MailjetMessage(
            html=html,
            subject=subject,
            recipient=recipient,
            user=user,
            email_type=type_,
            add_sender=True,
            employment=kwargs.get("employment"),
            attachment=attachment,
        )

    @contextmanager
    def _override_api_version(self, version):
        # API V3.1 does not handle contact subscriptions => we need to temporarily change client version (to V3) for this
        current_version = self.mailjet.config.version
        self.mailjet.config.version = version
        try:
            yield
        finally:
            self.mailjet.config.version = current_version

    # https://dev.mailjet.com/email/reference/contacts/subscriptions#v3_get_listrecipient
    def get_subscription_statuses(self, email):
        with self._override_api_version("v3"):
            try:
                response = self.mailjet.listrecipient.get(
                    filters=dict(ContactEmail=email, Limit=100),
                    timeout=MAILJET_API_REQUEST_TIMEOUT,
                )
                if response.status_code != 200:
                    raise ValueError(
                        f"Response status code {response.status_code}"
                    )

                response = response.json()
                statuses = {
                    k: MailjetSubscriptionStatus.NONE
                    for k in MailingContactList
                }
                if response["Count"] != 0:
                    for list_recipient in response["Data"]:
                        if list_recipient["ListID"] in statuses:
                            statuses[list_recipient["ListID"]] = (
                                MailjetSubscriptionStatus.UNSUBSCRIBED
                                if list_recipient["IsUnsubscribed"]
                                else MailjetSubscriptionStatus.SUBSCRIBED
                            )
                return statuses

            except Exception as e:
                raise SubscriptionRequestError(
                    f"Request for subscription info failed because : {e}"
                )

    # https://dev.mailjet.com/email/reference/contacts/subscriptions#v3_post_contactslist_list_ID_managecontact
    def _manage_email_subscription_to_contact_list(
        self, email, contact_list, action
    ):
        with self._override_api_version("v3"):
            try:
                response = self.mailjet.contactslist_managecontact.create(
                    id=MAILJET_CONTACT_LIST_IDS[contact_list],
                    data=dict(Action=action, Email=email),
                    timeout=MAILJET_API_REQUEST_TIMEOUT,
                )
                if response.status_code != 201:
                    raise ValueError(
                        f"Response status code {response.status_code}"
                    )

            except Exception as e:
                raise SubscriptionRequestError(
                    f"{'Subscription' if action == MailjetSubscriptionActions.SUBSCRIBE else 'Unsubscription'} request failed for email {email} because : {e}"
                )

    def subscribe_email_to_contact_list(self, email, contact_list):
        return self._manage_email_subscription_to_contact_list(
            email, contact_list, action=MailjetSubscriptionActions.SUBSCRIBE
        )

    def unsubscribe_email_to_contact_list(self, email, contact_list):
        return self._manage_email_subscription_to_contact_list(
            email,
            contact_list,
            action=MailjetSubscriptionActions.UNSUBSCRIBE,
        )

    def remove_email_from_contact_list(self, email, contact_list):
        return self._manage_email_subscription_to_contact_list(
            email, contact_list, action=MailjetSubscriptionActions.REMOVE
        )

    def generate_employee_invite(self, employment, reminder=False):
        if not employment.invite_token:
            raise ValueError(
                f"Cannot send invite for employment {employment} : it is already bound to a user"
            )

        if employment.user_id:
            invitation_link = f"{app.config['FRONTEND_URL']}/redeem_invite?token={employment.invite_token}"

        else:
            invitation_link = f"{app.config['FRONTEND_URL']}/invite?token={employment.invite_token}"

        company_name = employment.company.name
        subject = f"{'Rappel : ' if reminder else ''}{company_name} vous invite à rejoindre Mobilic."

        return Mailer._create_message_from_flask_template(
            "invitation_email.html",
            subject=subject,
            type_=EmailType.INVITATION,
            recipient=employment.user.email
            if employment.user
            else employment.email,
            user=employment.user,
            employment=employment,
            first_name=employment.user.first_name if employment.user else None,
            custom_id=employment.invite_token,
            invitation_link=Markup(invitation_link),
            company_name=company_name,
            reminder=reminder,
        )

    def send_employee_invite(self, employment, reminder=False):
        self._send_single(
            self.generate_employee_invite(employment, reminder=reminder),
            _disable_commit=True,
        )

    def batch_send_employee_invites(self, employments, reminder=False):
        messages = [
            self.generate_employee_invite(e, reminder=reminder)
            for e in employments
        ]
        self.send_batch(messages, _disable_commit=True)
        return messages

    def send_activation_email(
        self,
        user,
        is_employee=True,
        create_account=True,
        _disable_commit=False,
    ):
        if not user.email:
            raise ValueError(
                f"Cannot send activation email because user has no email address"
            )

        if not user.activation_email_token:
            user.create_activation_link()

        id = user.id

        token = jwt.encode(
            {
                "email": user.email,
                "expires_at": (
                    datetime.now()
                    + app.config["EMAIL_ACTIVATION_TOKEN_EXPIRATION"]
                ).timestamp(),
                "user_id": id,
                "token": user.activation_email_token,
            },
            app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        activation_link = (
            f"{app.config['FRONTEND_URL']}/activate_email?token={token}"
        )

        company = None
        has_admin_rights = None
        if create_account:
            employment = user.employments[0] if user.employments else None
            if employment:
                company = employment.company
                has_admin_rights = employment.has_admin_rights

        self._send_single(
            self._create_message_from_flask_template(
                "account_activation_email.html",
                subject="Activez votre compte Mobilic"
                if create_account
                else "Confirmez l'adresse email de votre compte Mobilic",
                type_=EmailType.ACCOUNT_ACTIVATION,
                user=user,
                user_id=Markup(id),
                first_name=user.first_name,
                create_account=create_account,
                activation_link=Markup(activation_link),
                company_name=company.name if company else None,
                has_admin_rights=has_admin_rights,
                is_employee=is_employee,
            ),
            _disable_commit=_disable_commit,
        )

    def send_company_creation_email(self, company, user):
        self._send_single(
            self._create_message_from_flask_template(
                "company_creation_email.html",
                subject=f"L'entreprise {company.name} est créée sur Mobilic !",
                user=user,
                type_=EmailType.COMPANY_CREATION,
                first_name=user.first_name,
                website_link=Markup(f"{app.config['FRONTEND_URL']}"),
                documentation_link=Markup(
                    f"{app.config['FRONTEND_URL']}/resources/admin"
                ),
                company_name=company.name,
                company_siren=Markup(company.siren),
                contact_email=Markup(CONTACT_ADDRESS),
            )
        )

    def send_companies_creation_email(self, companies, siren, user):
        subject = (
            f"{len(companies)} entreprises ont bien été créées sur Mobilic !"
        )
        self._send_single(
            self._create_message_from_flask_template(
                "companies_creation_email.html",
                subject=subject,
                user=user,
                type_=EmailType.COMPANY_CREATION,
                first_name=user.first_name,
                website_link=Markup(f"{app.config['FRONTEND_URL']}"),
                documentation_link=Markup(
                    f"{app.config['FRONTEND_URL']}/resources/admin"
                ),
                companies=companies,
                nb_companies=len(companies),
                companies_siren=Markup(siren),
                contact_email=Markup(CONTACT_ADDRESS),
            )
        )

    def send_employment_validation_email(self, employment):
        self._send_single(
            self._create_message_from_flask_template(
                "employment_validation_email.html",
                subject=f"Vous êtes à présent membre de l'entreprise {employment.company.name}",
                type_=EmailType.EMPLOYMENT_VALIDATION,
                user=employment.user,
                first_name=employment.user.first_name,
                company_name=employment.company.name,
            )
        )

    @staticmethod
    def _generate_reset_password_link(user):
        token = jwt.encode(
            {
                "user_id": user.id,
                "hash": user.password,
                "expires_at": (
                    datetime.now()
                    + app.config["RESET_PASSWORD_TOKEN_EXPIRATION"]
                ).timestamp(),
            },
            app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        return f"{app.config['FRONTEND_URL']}/reset_password?token={token}"

    def send_reset_password_email(self, user):
        reset_link = self._generate_reset_password_link(user)
        self._send_single(
            self._create_message_from_flask_template(
                "reset_password_email.html",
                subject="Réinitialisation de votre mot de passe Mobilic",
                user=user,
                type_=EmailType.RESET_PASSWORD,
                first_name=user.first_name,
                reset_link=Markup(reset_link),
            )
        )

    def _generate_third_party_software_account_email(
        self, third_party_client_employment, client_id, employment_id, **kwargs
    ):
        validation_link = f"{app.config['FRONTEND_URL']}/sync_employee?token={third_party_client_employment.invitation_token}&client_id={client_id}&employment_id={employment_id}"
        return self._create_message_from_flask_template(
            validation_link=Markup(validation_link), **kwargs
        )

    def generate_third_party_software_account_creation_email(
        self, third_party_client_employment, employment, client, user
    ):
        return self._generate_third_party_software_account_email(
            third_party_client_employment=third_party_client_employment,
            client_id=client.id,
            employment_id=employment.id,
            first_name=user.first_name,
            company_name=employment.company.name,
            software_name=client.name,
            user=user,
            type_=EmailType.THIRD_PARTY_ACCOUNT_CREATION,
            template="third_party_software_account_creation.html",
            subject="Valider votre compte Mobilic",
        )

    def generate_third_party_software_employment_creation_email(
        self, third_party_client_employment, employment, client, user
    ):
        return self._generate_third_party_software_account_email(
            third_party_client_employment=third_party_client_employment,
            client_id=client.id,
            employment_id=employment.id,
            first_name=user.first_name,
            company_name=employment.company.name,
            software_name=client.name,
            user=user,
            type_=EmailType.THIRD_PARTY_EMPLOYMENT_CREATION,
            template="third_party_software_employment.html",
            subject="Ouverture d'accès à votre compte Mobilic",
            employment_already_exists=False,
        )

    def generate_third_party_software_employment_access_email(
        self, third_party_client_employment, employment, client, user
    ):
        return self._generate_third_party_software_account_email(
            third_party_client_employment=third_party_client_employment,
            client_id=client.id,
            employment_id=employment.id,
            first_name=user.first_name,
            company_name=employment.company.name,
            software_name=client.name,
            user=user,
            type_=EmailType.THIRD_PARTY_EMPLOYMENT_ACCESS,
            template="third_party_software_employment.html",
            subject="Ouverture d'accès à votre compte Mobilic",
            employment_already_exists=True,
        )

    def generate_team_management_update_mail(
        self, user, submitter, team, access_given
    ):
        return self._create_message_from_flask_template(
            "team_update_affectation.html",
            type_=EmailType.TEAM_AFFECTATION,
            subject="Changement d'affectation de groupe Mobilic",
            user=user,
            first_name=user.first_name,
            access_given=access_given,
            team_name=team.name,
            company_name=team.company.name,
            submitter_first_name=submitter.first_name,
            submitter_last_name=submitter.last_name,
        )

    def generate_team_colleague_affectation_mail(self, user, new_admin, team):
        return self._create_message_from_flask_template(
            "team_colleague_affectation.html",
            type_=EmailType.TEAM_NEW_COLLEAGUE,
            subject="Ajout d'un responsable dans votre groupe Mobilic",
            user=user,
            first_name=user.first_name,
            new_admin_first_name=new_admin.first_name,
            new_admin_last_name=new_admin.last_name,
            team_name=team.name,
            company_name=team.company.name,
        )

    def send_warning_email_about_mission_changes(
        self,
        user,
        admin,
        mission,
        old_start_time,
        new_start_time,
        old_end_time,
        new_end_time,
        old_timers,
        new_timers,
        is_holiday,
    ):
        mission_day = to_fr_tz(old_start_time).strftime("%d/%m")

        if is_holiday:
            template = "holiday_changes_warning_email.html"
            subject = f"Modification de votre {mission.name.lower()} du {mission_day}"
            type_ = EmailType.HOLIDAY_CHANGES_WARNING
            old_work_duration = old_timers["total_service"]
            new_work_duration = (
                new_timers["total_service"]
                if new_timers["total_service"] != old_timers["total_service"]
                else None
            )
        else:
            template = "mission_changes_warning_email.html"
            subject = f"Modifications sur votre mission {mission.name} du {mission_day}"
            type_ = EmailType.MISSION_CHANGES_WARNING
            old_work_duration = old_timers["total_work"]
            new_work_duration = (
                new_timers["total_work"]
                if new_timers["total_work"] != old_timers["total_work"]
                else None
            )

        self._send_single(
            self._create_message_from_flask_template(
                template,
                subject=subject,
                user=user,
                type_=type_,
                first_name=user.first_name,
                mission_name=mission.name,
                company_name=mission.company.name,
                admin_full_name=admin.display_name,
                mission_day=Markup(mission_day),
                mission_link=Markup(
                    f"{app.config['FRONTEND_URL']}/app/history?mission={mission.id}"
                ),
                old_start_time=old_start_time,
                new_start_time=new_start_time
                if new_start_time != old_start_time
                else None,
                old_end_time=old_end_time,
                new_end_time=new_end_time
                if new_end_time != old_end_time
                else None,
                old_work_duration=old_work_duration,
                new_work_duration=new_work_duration,
                show_dates=len(
                    set(
                        [
                            dt.date()
                            for dt in [
                                to_fr_tz(new_end_time),
                                to_fr_tz(new_start_time),
                                to_fr_tz(old_start_time),
                                to_fr_tz(old_end_time),
                            ]
                        ]
                    )
                )
                > 1,
            ),
            _disable_commit=True,
        )

    def send_information_email_about_new_mission(
        self, user, admin, mission, start_time, end_time, timers
    ):
        start_time = to_fr_tz(start_time)
        end_time = to_fr_tz(end_time)
        mission_day = start_time.strftime("%d/%m")
        self._send_single(
            self._create_message_from_flask_template(
                "new_mission_information_email.html",
                subject=f"La mission {mission.name} du {mission_day} a été rajoutée à votre historique",
                user=user,
                type_=EmailType.NEW_MISSION_INFORMATION,
                first_name=user.first_name,
                mission_name=mission.name,
                company_name=mission.company.name,
                admin_full_name=admin.display_name,
                mission_day=Markup(mission_day),
                mission_link=Markup(
                    f"{app.config['FRONTEND_URL']}/app/history?mission={mission.id}"
                ),
                start_time=start_time,
                end_time=end_time,
                work_duration=timers["total_work"],
                show_dates=start_time.date() != end_time.date(),
            ),
            _disable_commit=True,
        )

    def send_worker_onboarding_first_email(self, user):
        self._send_single(
            self._create_message_from_mailjet_template(
                2690636,
                type_=EmailType.WORKER_ONBOARDING_FIRST_INFO,
                user=user,
                first_name=user.first_name,
                cta=f"{app.config['FRONTEND_URL']}/login",
                _disable_commit=True,
            ),
            _disable_commit=True,
        )

    def send_worker_onboarding_second_email(self, user):
        self._send_single(
            self._create_message_from_mailjet_template(
                2690445,
                type_=EmailType.WORKER_ONBOARDING_SECOND_INFO,
                user=user,
                first_name=user.first_name,
                cta=f"{app.config['FRONTEND_URL']}/login?next=/app/history",
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_admin_about_to_lose_certificate_email(
        self, company, user, attribution_date
    ):
        self._send_single(
            self._create_message_from_flask_template(
                template="companies_about_to_lose_certificate.html",
                subject="Attention, vous risquez de perdre le certificat Mobilic !",
                company_name=company.name,
                user=user,
                attribution_date=attribution_date,
                type_=EmailType.COMPANY_ABOUT_TO_LOSE_CERTIFICATE,
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_manager_onboarding_first_email(self, user):
        self._send_single(
            self._create_message_from_mailjet_template(
                2690876,
                type_=EmailType.MANAGER_ONBOARDING_FIRST_INFO,
                user=user,
                first_name=user.first_name,
                cta=f"{app.config['FRONTEND_URL']}/login?next=/admin/company",
                _disable_commit=True,
            ),
            _disable_commit=True,
        )

    def send_blocked_account_email(self, user):
        reset_link = self._generate_reset_password_link(user)
        self._send_single(
            self._create_message_from_flask_template(
                "account_blocked_email.html",
                subject="Débloquer votre compte Mobilic",
                user=user,
                type_=EmailType.BLOCKED_ACCOUNT,
                first_name=user.first_name,
                reset_link=Markup(reset_link),
                nb_max_tries=app.config[
                    "NB_BAD_PASSWORD_TRIES_BEFORE_BLOCKING"
                ],
            )
        )

    def send_companies_without_invitations_email(self, employment):
        self._send_single(
            self._create_message_from_flask_template(
                template="company_without_any_invitation.html",
                subject="Commencez à utiliser Mobilic en invitant vos salariés !",
                employment=employment,
                user=employment.user,
                type_=EmailType.COMPANY_WITHOUT_ANY_INVITATION,
                interface_link=Markup(
                    f"{app.config['FRONTEND_URL']}/admin/company"
                ),
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_active_then_inactive_companies_email(self, admin):
        self._send_single(
            self._create_message_from_flask_template(
                template="active_then_inactive_companies.html",
                subject="Votre activité sur Mobilic peut vous mener à l’obtention du certificat",
                user=admin,
                type_=EmailType.COMPANY_ACTIVE_THEN_INACTIVE,
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_worker_holiday_logging_notification(
        self, admin, user, company, title, periods
    ):
        history_link = Markup(
            f"{app.config['FRONTEND_URL']}/app/history?day={periods[0][0].strftime('%Y-%m-%d')}"
        )
        self._send_single(
            self._create_message_from_flask_template(
                template="holiday_logging_email.html",
                user=user,
                subject="Enregistrement d’un congé ou d’une absence par votre gestionnaire",
                type_=EmailType.HOLIDAY_LOGGING_BY_ADMIN,
                history_link=history_link,
                admin_full_name=admin.display_name,
                company_name=company.name,
                title=title,
                periods=periods,
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_admin_employee_rejects_cgu_email(self, admins, employee):
        for admin in admins:
            self._send_single(
                self._create_message_from_flask_template(
                    template="cgu_employee_rejected.html",
                    subject="Suppression prochaine du compte d’un salarié",
                    user=admin,
                    type_=EmailType.EMPLOYEE_REJECTS_CGU,
                    employee_full_name=employee.display_name,
                    employee_id=employee.id,
                    release_date=app.config["CGU_RELEASE_DATE"],
                ),
                _apply_whitelist_if_not_prod=True,
            )

    def send_admin_company_suspended_cgu_email(self, admin):
        self._send_single(
            self._create_message_from_flask_template(
                template="cgu_suspended_company.html",
                subject="Suppression de votre compte entreprise Mobilic",
                user=admin,
                type_=EmailType.COMPANY_SUSPENDED_CGU,
                release_date=app.config["CGU_RELEASE_DATE"],
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_cgu_expiry_warning_email(self, user, expiry_date, is_admin):
        self._send_single(
            self._create_message_from_flask_template(
                template="cgu_warning_suspension.html",
                subject="Votre compte Mobilic sera supprimé dans 72 heures",
                user=user,
                type_=EmailType.EXPIRY_WARNING_CGU,
                is_admin=is_admin,
                expiry_date=expiry_date,
            ),
            _apply_whitelist_if_not_prod=True,
        )

    def send_export_excel(
        self, user, company_name, file, subject_suffix="", is_admin=True
    ):
        subject = (
            f"Téléchargement des données Mobilic de l’entreprise {company_name}"
            if is_admin
            else "Téléchargement de vos temps de travail saisis dans Mobilic"
        )
        self._send_single(
            self._create_message_from_flask_template(
                template="admin_export_excel.html"
                if is_admin
                else "employee_export_excel.html",
                user=user,
                subject=f"{subject}{subject_suffix}",
                type_=EmailType.ADMIN_EXPORT_EXCEL
                if is_admin
                else EmailType.EMPLOYEE_EXPORT_EXCEL,
                attachment=file,
            ),
            _apply_whitelist_if_not_prod=False,
        )


mailer = Mailer()
