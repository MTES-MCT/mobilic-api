from flask import jsonify
from webargs import fields
from flask_apispec import use_kwargs
from marshmallow import Schema

from app import app, mailer
from app.helpers.authentication import (
    optional_auth,
    current_user,
    require_auth,
)
from app.helpers.mail import MailjetError
from app.helpers.validation import (
    validate_clean_email_string,
    clean_email_string,
)


class EmailSchema(Schema):
    email = fields.String(
        required=False,
        validate=lambda s: validate_clean_email_string(clean_email_string(s)),
    )


@app.route("/contacts/subscribe_to_newsletter", methods=["POST"])
@use_kwargs(EmailSchema(), apply=True)
@optional_auth
def subscribe_to_newsletter(email=None):
    if not current_user and not email:
        return (
            jsonify(
                {
                    "error": "No email address nor an auth token was provided for subscription to the newsletter"
                }
            ),
            400,
        )
    actual_email = current_user.email if current_user else email
    try:
        mailer.subscribe_email_to_contact_list(actual_email)
    except MailjetError as e:
        return jsonify({"error": e.message}), 500
    return jsonify({"success": True}), 200


@app.route("/contacts/unsubscribe_from_newsletter", methods=["POST"])
@require_auth
def unsubscribe_from_newsletter():
    try:
        mailer.unsubscribe_email_to_contact_list(current_user.email)
    except MailjetError as e:
        return jsonify({"error": e.message}), 500
    return jsonify({"success": True}), 200
