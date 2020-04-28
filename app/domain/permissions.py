from app.models import Company, User


def company_admin(actor, company_obj_or_id):
    return actor.is_company_admin and belongs_to_company(
        actor, company_obj_or_id
    )


def belongs_to_company(actor, company_obj_or_id):
    company_id = company_obj_or_id
    if type(company_obj_or_id) is Company:
        company_id = company_obj_or_id.id
    return actor.company_id == company_id


def self_or_company_admin(actor, user_obj_or_id):
    user = user_obj_or_id
    if type(user_obj_or_id) is int:
        user = User.query.get(user_obj_or_id)
    if not user or not type(user) is User:
        return False
    return actor == user or company_admin(actor, user.company_id)


def can_submitter_log_for_user(submitter, user):
    return submitter.company_id == user.company_id


def can_submitter_log_on_mission(submitter, mission):
    return submitter == mission.submitter or submitter.id in [
        a.user_id for a in mission.activities
    ]
