from flask import g
from app.models import User, Employment
from sqlalchemy import func

from app import app, db
from app.models import User, Employment


def create_user(
    first_name,
    last_name,
    timezone_name=None,
    email=None,
    password=None,
    invite_token=None,
    ssn=None,
    fc_info=None,
):
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=password,
        ssn=ssn,
        timezone_name=timezone_name,
        has_confirmed_email=True if not fc_info else False,
        france_connect_info=fc_info,
        france_connect_id=fc_info.get("sub") if fc_info else None,
    )
    db.session.add(user)
    db.session.flush()

    company = None

    # if we have an invite_token, try to find employment based on it
    if invite_token:
        employment_to_validate = Employment.query.filter(
            Employment.invite_token == invite_token,
            Employment.user_id.is_(None),
        ).one_or_none()

        if not employment_to_validate:
            app.logger.warning(
                f"Could not find valid employment matching token {invite_token}"
            )
        # we found the employment, let's accept it for the user
        else:
            employment_to_validate.bind(user)
            employment_to_validate.validate_by(user)
            company = employment_to_validate.company

    # in case we don't have an invite_token, let's try to find an employment based on the user email
    else:
        employments_to_attach = Employment.query.filter(
            func.lower(Employment.email) == func.lower(email),
            Employment.user_id.is_(None),
        ).all()

        for employment in employments_to_attach:
            employment.bind(user)

    message = f"Signed up new user {user}"
    if company:
        message += f" of company {company}"

    g.user = user
    app.logger.info(
        message,
        extra={
            "post_to_mattermost": True,
            "log_title": "New user signup",
            "emoji": ":tada:",
        },
    )

    return user


def get_user_from_fc_info(fc_info):
    france_connect_id = fc_info.get("sub")

    return User.query.filter(
        User.france_connect_id == france_connect_id
    ).one_or_none()
