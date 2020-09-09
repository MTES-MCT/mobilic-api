from mailjet_rest import Client
import jwt
from flask import render_template
from datetime import datetime, date

from app.helpers.errors import MailjetError

SENDER_ADDRESS = "mobilic@beta.gouv.fr"
SENDER_NAME = "Mobilic"


class Mailer:
    def __init__(self, config, dry_run=False):
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
                raise MailjetError(
                    f"Attempt to send mail via Mailjet failed with error : {response.json()}"
                )

    def _send_email_from_template(
        self, template, subject, recipient, **kwargs
    ):
        html = render_template(template, **kwargs)
        self._send(html, subject, recipient, kwargs.get("custom_id"))

    def send_employee_invite(self, employment, recipient, first_name=None):
        if employment.user_id or not employment.invite_token:
            raise ValueError(
                f"Cannot send invite for employment {employment} : it is already bound to a user"
            )

        invitation_link = f"{self.app_config['FRONTEND_URL']}/invite?token={employment.invite_token}"
        company_name = employment.company.name
        subject = f"{company_name} vous invite à rejoindre Mobilic."

        self._send_email_from_template(
            "invitation_email.html",
            subject,
            recipient,
            first_name=first_name,
            custom_id=employment.invite_token,
            invitation_link=invitation_link,
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
            user_id=id,
            first_name=user.first_name,
            create_account=create_account,
            activation_link=activation_link,
            company_name=company.name if company else None,
            has_admin_rights=has_admin_rights,
        )

    def send_company_creation_email(self, company, user):
        self._send_email_from_template(
            "company_creation_email.html",
            f"L'entreprise {company.name} est créée sur Mobilic !",
            user.email,
            first_name=user.first_name,
            company_name=company.name,
            company_siren=company.siren,
        )

    def send_employment_validation_email(self, employment):
        self._send_email_from_template(
            "employment_validation_email.html",
            f"Vous êtes à présent membre de l'entreprise {employment.company.name}",
            employment.user.email,
            first_name=employment.user.first_name,
            company_name=employment.company.name,
        )
