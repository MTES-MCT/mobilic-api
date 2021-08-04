from mailjet_rest import Client
import jwt
import os
from flask import render_template
from datetime import datetime, date
from markupsafe import Markup

from app.helpers.errors import MailjetError
from app.helpers.time import to_fr_tz
from app.helpers.mail_type import EmailType

SENDER_ADDRESS = "mobilic@beta.gouv.fr"
SENDER_NAME = "Mobilic"

env = os.environ.get("MOBILIC_ENV", "dev")


class InvalidEmailAddressError(MailjetError):
    code = "INVALID_EMAIL_ADDRESS"


# Mailjet is used as the email solution : what follows is the wrapper of their API, whose doc is here : https://github.com/mailjet/mailjet-apiv3-python
class Mailer:
    def __init__(self, app):
        config = app.config
        self.mailjet = Client(
            auth=(config["MAILJET_API_KEY"], config["MAILJET_API_SECRET"]),
            version="v3.1",
        )
        self.app_config = config

    @staticmethod
    def _retrieve_mailjet_id_or_handle_error(response, recipient):
        if response.status_code == 200:
            return response.json()["Messages"][0]["To"][0]["MessageID"]

        if not response.status_code == 200:
            try:
                response_payload = response.json()["Messages"][0]

                if response_payload["Status"] == "error":
                    if any(
                        [
                            e["ErrorCode"] == "mj-0013"
                            for e in response_payload["Errors"]
                        ]
                    ):
                        raise InvalidEmailAddressError(
                            f"Mailjet could not send email to invalid address : {recipient}"
                        )
            except MailjetError as e:
                raise e
            except Exception:
                pass
            raise MailjetError(
                f"Attempt to send mail via Mailjet failed with error : {response.json()}"
            )

    def _send(
        self,
        message,
        subject,
        type_,
        user=None,
        recipient=None,
        add_sender=True,
        _disable_commit=False,
        **kwargs,
    ):
        from app.models import Email
        from app import db

        actual_recipient = user.email if user else recipient

        message = {**message, "To": [{"Email": actual_recipient}]}
        if add_sender:
            message["From"] = {"Email": SENDER_ADDRESS, "Name": SENDER_NAME}
        if subject:
            message["Subject"] = subject

        response = self.mailjet.send.create(data={"Messages": [message]})
        mailjet_id = self._retrieve_mailjet_id_or_handle_error(
            response, actual_recipient
        )
        db.session.add(
            Email(
                mailjet_id=mailjet_id,
                address=actual_recipient,
                user=user,
                type=type_,
                employment=kwargs.get("employment"),
            )
        )
        db.session.commit() if not _disable_commit else db.session.flush()

    def _send_email_from_mailjet_template(
        self,
        template_id,
        type_,
        subject=None,
        recipient=None,
        user=None,
        _disable_commit=False,
        **kwargs,
    ):
        message = {
            "TemplateID": template_id,
            "TemplateLanguage": True,
            "Variables": kwargs,
        }
        self._send(
            message,
            subject=subject,
            recipient=recipient,
            user=user,
            type_=type_,
            add_sender=False,
            _disable_commit=_disable_commit,
            employment=kwargs.get("employment"),
        )

    def _send_email_from_flask_template(
        self,
        template,
        type_,
        subject,
        recipient=None,
        user=None,
        _disable_commit=False,
        **kwargs,
    ):
        html = render_template(template, **kwargs)
        self._send(
            {"HTMLPart": html},
            subject=subject,
            recipient=recipient,
            user=user,
            type_=type_,
            add_sender=True,
            _disable_commit=_disable_commit,
            employment=kwargs.get("employment"),
        )

    def send_employee_invite(self, employment, recipient):
        if not employment.invite_token:
            raise ValueError(
                f"Cannot send invite for employment {employment} : it is already bound to a user"
            )

        if employment.user_id:
            invitation_link = f"{self.app_config['FRONTEND_URL']}/redeem_invite?token={employment.invite_token}"

        else:
            invitation_link = f"{self.app_config['FRONTEND_URL']}/invite?token={employment.invite_token}"

        company_name = employment.company.name
        subject = f"{company_name} vous invite à rejoindre Mobilic."

        self._send_email_from_flask_template(
            "invitation_email.html",
            subject=subject,
            type_=EmailType.INVITATION,
            recipient=recipient,
            user=employment.user,
            employment=employment,
            first_name=employment.user.first_name if employment.user else None,
            custom_id=employment.invite_token,
            invitation_link=Markup(invitation_link),
            company_name=company_name,
            _disable_commit=True,
        )

    def send_activation_email(self, user, create_account=True):
        if not user.email:
            raise ValueError(
                f"Cannot send activation email because user has no email address"
            )

        id = user.id

        token = jwt.encode(
            {
                "email": user.email,
                "expires_at": (
                    datetime.now()
                    + self.app_config["EMAIL_ACTIVATION_TOKEN_EXPIRATION"]
                ).timestamp(),
                "user_id": id,
                "token": user.activation_email_token,
            },
            self.app_config["JWT_SECRET_KEY"],
            algorithm="HS256",
        ).decode("utf-8")
        activation_link = (
            f"{self.app_config['FRONTEND_URL']}/activate_email?token={token}"
        )

        company = None
        has_admin_rights = None
        primary_employment = user.primary_employment_at(date.today())
        if primary_employment:
            company = primary_employment.company
            has_admin_rights = primary_employment.has_admin_rights

        self._send_email_from_flask_template(
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
        )

    def send_company_creation_email(self, company, user):
        self._send_email_from_flask_template(
            "company_creation_email.html",
            subject=f"L'entreprise {company.name} est créée sur Mobilic !",
            user=user,
            type_=EmailType.COMPANY_CREATION,
            first_name=user.first_name,
            website_link=Markup(self.app_config["FRONTEND_URL"]),
            company_name=company.name,
            company_siren=Markup(company.siren),
            contact_email=Markup(SENDER_ADDRESS),
            contact_phone=Markup("+33 6 89 56 58 97"),
        )

    def send_employment_validation_email(self, employment):
        self._send_email_from_flask_template(
            "employment_validation_email.html",
            subject=f"Vous êtes à présent membre de l'entreprise {employment.company.name}",
            type_=EmailType.EMPLOYMENT_VALIDATION,
            user=employment.user,
            first_name=employment.user.first_name,
            company_name=employment.company.name,
        )

    def send_reset_password_email(self, user):
        token = jwt.encode(
            {
                "user_id": user.id,
                "hash": user.password,
                "expires_at": (
                    datetime.now()
                    + self.app_config["RESET_PASSWORD_TOKEN_EXPIRATION"]
                ).timestamp(),
            },
            self.app_config["JWT_SECRET_KEY"],
            algorithm="HS256",
        ).decode("utf-8")
        reset_link = (
            f"{self.app_config['FRONTEND_URL']}/reset_password?token={token}"
        )
        self._send_email_from_flask_template(
            "reset_password_email.html",
            subject="Réinitialisation de votre mot de passe Mobilic",
            user=user,
            type_=EmailType.RESET_PASSWORD,
            first_name=user.first_name,
            reset_link=Markup(reset_link),
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
    ):
        old_start_time = to_fr_tz(old_start_time)
        old_end_time = to_fr_tz(old_end_time)
        new_start_time = to_fr_tz(new_start_time)
        new_end_time = to_fr_tz(new_end_time)
        self._send_email_from_flask_template(
            "mission_changes_warning_email.html",
            subject=f"Modifications sur votre mission {mission.name} du {old_start_time.strftime('%d/%m')}",
            user=user,
            type_=EmailType.MISSION_CHANGES_WARNING,
            first_name=user.first_name,
            mission_name=mission.name,
            company_name=mission.company.name,
            admin_full_name=admin.display_name,
            mission_day=Markup(old_start_time.strftime("%d/%m")),
            mission_link=Markup(
                f"{self.app_config['FRONTEND_URL']}/app/history?mission={mission.id}"
            ),
            old_start_time=old_start_time,
            new_start_time=new_start_time
            if new_start_time != old_start_time
            else None,
            old_end_time=old_end_time,
            new_end_time=new_end_time
            if new_end_time != old_end_time
            else None,
            old_work_duration=old_timers["total_work"],
            new_work_duration=new_timers["total_work"]
            if new_timers["total_work"] != old_timers["total_work"]
            else None,
            show_dates=len(
                set(
                    [
                        dt.date()
                        for dt in [
                            new_end_time,
                            new_start_time,
                            old_start_time,
                            old_end_time,
                        ]
                    ]
                )
            )
            > 1,
        )

    def send_information_email_about_new_mission(
        self, user, admin, mission, start_time, end_time, timers
    ):
        start_time = to_fr_tz(start_time)
        end_time = to_fr_tz(end_time)
        mission_day = start_time.strftime("%d/%m")
        self._send_email_from_flask_template(
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
                f"{self.app_config['FRONTEND_URL']}/app/history?mission={mission.id}"
            ),
            start_time=start_time,
            end_time=end_time,
            work_duration=timers["total_work"],
            show_dates=start_time.date() != end_time.date(),
        )

    def send_worker_onboarding_first_email(self, user):
        self._send_email_from_mailjet_template(
            2690636,
            type_=EmailType.WORKER_ONBOARDING_FIRST_INFO,
            user=user,
            first_name=user.first_name,
            cta=f"{self.app_config['FRONTEND_URL']}/login?next=/app",
        )

    def send_worker_onboarding_second_email(self, user):
        self._send_email_from_mailjet_template(
            2690445,
            type_=EmailType.WORKER_ONBOARDING_SECOND_INFO,
            user=user,
            first_name=user.first_name,
            cta=f"{self.app_config['FRONTEND_URL']}/login?next=/app/history",
        )

    def send_manager_onboarding_first_email(self, user, company):
        self._send_email_from_mailjet_template(
            2690876,
            type_=EmailType.MANAGER_ONBOARDING_FIRST_INFO,
            user=user,
            first_name=user.first_name,
            company=company.name,
            cta=f"{self.app_config['FRONTEND_URL']}/login?next=/admin/company",
        )

    def send_manager_onboarding_second_email(self, user):
        self._send_email_from_mailjet_template(
            2690590,
            type_=EmailType.MANAGER_ONBOARDING_SECOND_INFO,
            user=user,
            first_name=user.first_name,
            cta=f"{self.app_config['FRONTEND_URL']}/login?next=/admin/company",
        )
