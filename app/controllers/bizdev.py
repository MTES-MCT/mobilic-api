from flask import make_response, jsonify
from flask_apispec import doc, use_kwargs
from webargs import fields

from app import app, mailer
from app.models import Company
from app.helpers.authorization import with_authorization_policy
from app.domain.permissions import company_admin
from app.helpers.validation import validate_clean_email_string


@app.route("/bizdev/invite_companies", methods=["POST"])
@doc(description="Faire connaître Mobilic à d'autres entreprises")
@use_kwargs(
    {
        "emails": fields.List(
            fields.String(),
            required=True,
            validate=lambda l: all(
                [validate_clean_email_string(email) for email in l]
            ),
        ),
        "company_id": fields.Int(required=True),
    },
    apply=True,
)
@with_authorization_policy(
    company_admin,
    get_target_from_args=lambda *args, **kwargs: kwargs["company_id"],
)
def invite_companies(emails, company_id):
    company = Company.query.get(company_id)
    for email in emails:
        mailer.send_email_discover_mobilic(
            from_company=company, to_email=email
        )
    response = make_response(jsonify({"result": "ok"}), 200)
    response.headers["Content-Type"] = "application/json"
    return response
