from flask import jsonify
from webargs import fields
from flask_apispec import use_kwargs
from marshmallow import Schema, validate

from app import app, mailer
from app.helpers.authentication import (
    optional_auth,
    current_user,
)
from app.helpers.mail import MailjetError, MailingContactList
from app.helpers.validation import (
    validate_clean_email_string,
    clean_email_string,
)


class NLSubscriptionSchema(Schema):
    email = fields.String(
        required=False,
        validate=lambda s: validate_clean_email_string(clean_email_string(s)),
    )
    list = fields.String(
        required=True,
        validate=validate.OneOf(list(MailingContactList.__members__.values())),
    )


@app.route("/contacts/subscribe-to-newsletter", methods=["POST"])
@use_kwargs(NLSubscriptionSchema(), apply=True)
@optional_auth
def subscribe_to_newsletter(list, email=None):
    if not current_user and not email:
        return (
            jsonify(
                {
                    "error": "No email address nor an auth token was provided for subscription to the newsletter"
                }
            ),
            400,
        )
    try:
        if current_user:
            current_user.subscribe_to_contact_list(list)
        else:
            mailer.subscribe_email_to_contact_list(email, list)
    except MailjetError as e:
        return jsonify({"error": e.message}), 500
    return jsonify({"success": True}), 200
