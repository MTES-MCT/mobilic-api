from mailjet_rest import Client
from flask import render_template

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

    def send_employee_invite(self, employment, recipient):
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
            custom_id=employment.invite_token,
            invitation_link=invitation_link,
            company_name=company_name,
        )
