from datetime import datetime
from sqlalchemy import extract
from app.models.certificate_info_result import (
    CertificateInfoResult,
    CertificateInfoAction,
)


def get_certificate_info_results_query_for_user_this_month(user_id):
    current_month = datetime.now().month
    return CertificateInfoResult.query.filter(
        CertificateInfoResult.user_id == user_id,
        extract("month", CertificateInfoResult.creation_time) == current_month,
    )


def check_result_already_exists_this_month(user_id, action, scenario):
    existing_action_result = (
        get_certificate_info_results_query_for_user_this_month(user_id=user_id)
        .filter(
            CertificateInfoResult.action == action,
            CertificateInfoResult.scenario == scenario,
        )
        .first()
    )
    return existing_action_result is not None


def has_scenario_been_resolved_this_month(user_id):
    action_result = (
        get_certificate_info_results_query_for_user_this_month(user_id=user_id)
        .filter(
            CertificateInfoResult.action.in_(
                [CertificateInfoAction.SUCCESS, CertificateInfoAction.CLOSE]
            )
        )
        .first()
    )
    return action_result is not None


def has_scenario_been_loaded_this_month(user_id):
    action_result = (
        get_certificate_info_results_query_for_user_this_month(user_id=user_id)
        .filter(CertificateInfoResult.action == CertificateInfoAction.LOAD)
        .first()
    )
    return action_result is not None


def has_scenario_been_succeeded_this_month(user_id):
    action_result = (
        get_certificate_info_results_query_for_user_this_month(user_id=user_id)
        .filter(CertificateInfoResult.action == CertificateInfoAction.SUCCESS)
        .first()
    )
    return action_result is not None


def has_scenario_been_closed_this_month(user_id):
    action_result = (
        get_certificate_info_results_query_for_user_this_month(user_id=user_id)
        .filter(
            CertificateInfoResult.action == CertificateInfoAction.CLOSE,
        )
        .first()
    )
    return action_result is not None
