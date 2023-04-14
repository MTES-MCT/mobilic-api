from datetime import datetime, date

from flask import g
from sqlalchemy import func

from app import app, db, mailer
from app.models import User, Employment
from app.models.user import UserAccountStatus


def create_user_by_third_party_if_needed(
    email,
    first_name,
    last_name,
    timezone_name=None,
):
    existing_user = User.query.filter(User.email == email).one_or_none()
    if existing_user:
        return existing_user, False
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        timezone_name=timezone_name,
        status=UserAccountStatus.THIRD_PARTY_PENDING_APPROVAL,
    )

    db.session.add(user)
    db.session.flush()
    return user, True


def create_user(
    first_name,
    last_name,
    timezone_name=None,
    email=None,
    password=None,
    invite_token=None,
    ssn=None,
    fc_info=None,
    way_heard_of_mobilic=None,
):
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=password,
        password_update_time=datetime.now(),
        ssn=ssn,
        timezone_name=timezone_name,
        has_confirmed_email=True if not fc_info else False,
        france_connect_info=fc_info,
        france_connect_id=fc_info.get("sub") if fc_info else None,
        way_heard_of_mobilic=way_heard_of_mobilic,
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
        bind_user_to_pending_employments(user)

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


def bind_user_to_pending_employments(user):
    employments_to_attach = Employment.query.filter(
        func.lower(Employment.email) == func.lower(user.email),
        Employment.user_id.is_(None),
    ).all()

    for employment in employments_to_attach:
        employment.bind(user)


def activate_user(user):
    user.has_confirmed_email = True
    user.has_activated_email = True


def increment_user_password_tries(user):
    user.nb_bad_password_tries = user.nb_bad_password_tries + 1
    if (
        user.nb_bad_password_tries
        >= app.config["NB_BAD_PASSWORD_TRIES_BEFORE_BLOCKING"]
    ):
        user.status = UserAccountStatus.BLOCKED_BAD_PASSWORD
        mailer.send_blocked_account_email(user)


def reset_user_password_tries(user):
    user.nb_bad_password_tries = 0


def change_user_password(user, new_password, revoke_tokens=True):
    if revoke_tokens:
        user.revoke_all_tokens()
    user.password = new_password
    user.password_update_time = datetime.now()
    user.nb_bad_password_tries = 0
    user.status = UserAccountStatus.ACTIVE


def is_user_related_to_onboarding_excluded_company(user):
    all_related_company_ids = [
        e.company_id
        for e in user.active_employments_at(
            date.today(), include_pending_ones=True
        )
    ]
    user_related_to_excluded_company = any(
        company_id in all_related_company_ids
        for company_id in app.config["COMPANY_EXCLUDE_ONBOARDING_EMAILS"]
    )
    return user_related_to_excluded_company
