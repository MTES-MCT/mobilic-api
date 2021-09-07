from flask import jsonify
from webargs import fields
from flask_apispec import use_kwargs
from marshmallow import Schema, validate
from enum import Enum

from app import app, mailer
from app.helpers.authentication import (
    optional_auth,
    current_user,
    require_auth,
)
from app.helpers.mail import MailjetError, MailjetContactLists
from app.helpers.validation import (
    validate_clean_email_string,
    clean_email_string,
)


# Careful when modifying this : the keys represent the possible values that are expected by the subscription endpoint
class SubscriptionMapEnum(int, Enum):
    EMPLOYEE = MailjetContactLists.NL_EMPLOYEES
    ADMIN = MailjetContactLists.NL_ADMINS
    CONTROLLER = MailjetContactLists.NL_CONTROLLERS
    SOFTWARE = MailjetContactLists.NL_SOFTWARES


class NLSubscriptionSchema(Schema):
    email = fields.String(
        required=False,
        validate=lambda s: validate_clean_email_string(clean_email_string(s)),
    )
    type = fields.String(
        required=True,
        validate=validate.OneOf(list(SubscriptionMapEnum.__members__.keys())),
    )


@app.route("/contacts/subscribe_to_newsletter", methods=["POST"])
@use_kwargs(NLSubscriptionSchema(), apply=True)
@optional_auth
def subscribe_to_newsletter(type, email=None):
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
        mailer.subscribe_email_to_contact_list(
            actual_email, SubscriptionMapEnum.__members__[type].value
        )
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
