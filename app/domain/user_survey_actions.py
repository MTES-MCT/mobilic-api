from app.models import UserSurveyActions
from app import db


def create_action_for_user(user_id, survey_id, action):
    db.session.add(
        UserSurveyActions(user_id=user_id, action=action, survey_id=survey_id)
    )
    db.session.commit()


def get_all_survey_actions_for_user(user_id):
    return UserSurveyActions.query.filter(
        UserSurveyActions.user_id == user_id
    ).all()
