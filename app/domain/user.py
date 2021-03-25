from flask import g

from app import app, db
from app.models import User, Employment


def create_user(
    first_name,
    last_name,
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
        has_confirmed_email=True if not fc_info else False,
        france_connect_info=fc_info,
        france_connect_id=fc_info.get("sub") if fc_info else None,
    )
    db.session.add(user)
    db.session.flush()

    company = None
    if invite_token:
        employment_to_validate = Employment.query.filter(
            Employment.invite_token == invite_token,
            Employment.user_id.is_(None),
        ).one_or_none()

        if not employment_to_validate:
            app.logger.warning(
                f"Could not find valid employment matching token {invite_token}"
            )
        else:
            if employment_to_validate.is_primary is None:
                employment_to_validate.is_primary = True
            employment_to_validate.bind(user)
            employment_to_validate.validate_by(user)
            company = employment_to_validate.company

    message = f"Signed up new user {user}"
    if company:
        message += f" of company {company}"

    g.user = user
    app.logger.info(
        message, extra={"post_to_slack": True, "emoji": ":tada:"},
    )

    return user


def get_user_from_fc_info(fc_info):
    france_connect_id = fc_info.get("sub")

    return User.query.filter(
        User.france_connect_id == france_connect_id
    ).one_or_none()
