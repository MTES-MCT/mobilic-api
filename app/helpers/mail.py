from mailjet_rest import Client
import jwt
from flask import render_template
from datetime import datetime, date
from markupsafe import Markup

from app.helpers.errors import MailjetError
from app.helpers.time import utc_to_fr

SENDER_ADDRESS = "mobilic@beta.gouv.fr"
SENDER_NAME = "Mobilic"


class InvalidEmailAddressError(MailjetError):
    code = "INVALID_EMAIL_ADDRESS"


def format_seconds_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h{minutes if minutes >= 10 else '0' + str(minutes)}"


class Mailer:
    def __init__(self, app, dry_run=False):
        config = app.config
        app.template_filter("format_duration")(format_seconds_duration)
        self.mailjet = Client(
            auth=(config["MAILJET_API_KEY"], config["MAILJET_API_SECRET"]),
            version="v3.1",
        )
        self.app_config = config
        self.dry_run = dry_run

    def _send(self, html, subject, recipient, custom_id=None):
        if not self.dry_run:
            message = {
                "From": {"Email": SENDER_ADDRESS, "Name": SENDER_NAME},
                "To": [{"Email": recipient}],
                "Subject": subject,
                "HTMLPart": html,
                "CustomId": custom_id or "",
            }
            response = self.mailjet.send.create(data={"Messages": [message]})
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
                except Exception as e:
                    pass
                raise MailjetError(
                    f"Attempt to send mail via Mailjet failed with error : {response.json()}"
                )

    def _send_email_from_template(
        self, template, subject, recipient, **kwargs
    ):
        html = render_template(template, **kwargs)
        self._send(html, subject, recipient, kwargs.get("custom_id"))

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

        self._send_email_from_template(
            "invitation_email.html",
            subject,
            recipient,
            first_name=employment.user.first_name if employment.user else None,
            custom_id=employment.invite_token,
            invitation_link=Markup(invitation_link),
            company_name=company_name,
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

        self._send_email_from_template(
            "account_activation_email.html",
            "Activez votre compte Mobilic"
            if create_account
            else "Confirmez l'adresse email de votre compte Mobilic",
            user.email,
            user_id=Markup(id),
            first_name=user.first_name,
            create_account=create_account,
            activation_link=Markup(activation_link),
            company_name=company.name if company else None,
            has_admin_rights=has_admin_rights,
        )

    def send_company_creation_email(self, company, user):
        self._send_email_from_template(
            "company_creation_email.html",
            f"L'entreprise {company.name} est créée sur Mobilic !",
            user.email,
            first_name=user.first_name,
            website_link=Markup(self.app_config["FRONTEND_URL"]),
            company_name=company.name,
            company_siren=Markup(company.siren),
            contact_email=Markup(SENDER_ADDRESS),
            contact_phone=Markup("+33 6 89 56 58 97"),
        )

    def send_employment_validation_email(self, employment):
        self._send_email_from_template(
            "employment_validation_email.html",
            f"Vous êtes à présent membre de l'entreprise {employment.company.name}",
            employment.user.email,
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
        self._send_email_from_template(
            "reset_password_email.html",
            "Réinitialisation de votre mot de passe Mobilic",
            user.email,
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
        old_start_time = utc_to_fr(old_start_time)
        old_end_time = utc_to_fr(old_end_time)
        new_start_time = utc_to_fr(new_start_time)
        new_end_time = utc_to_fr(new_end_time)
        self._send_email_from_template(
            "mission_changes_warning_email.html",
            f"Modifications sur votre mission {mission.name} du {old_start_time.strftime('%d/%m')}",
            user.email,
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
        )
