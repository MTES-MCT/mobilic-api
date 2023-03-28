from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from app.helpers.time import is_sunday_or_bank_holiday

from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.pdf import generate_pdf_from_template, Column
from app.helpers.time import to_fr_tz
from app.models.activity import ActivityType
from app.models.expenditure import ExpenditureType
from app.models.mission import UserMissionModificationStatus
from app.templates.filters import format_seconds_duration, format_time


def _get_summary_columns(include_support=False, include_expenditures=False):
    summary_columns = [
        Column(name="worked_days", label="Jours travaillés", color="#CFDAC8"),
        Column(
            name=ActivityType.DRIVE.value,
            label="Conduite",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
        Column(
            name=ActivityType.WORK.value,
            label="Autre tâche",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
    ]

    if include_support:
        summary_columns.append(
            Column(
                name=ActivityType.SUPPORT.value,
                label="Accompagnement",
                color="#C9CBFF",
                secondary=True,
                format=format_seconds_duration,
            )
        )

    summary_columns.append(
        Column(
            name="total_work",
            label="Heures travaillées",
            color="#C9CBFF",
            format=format_seconds_duration,
        )
    )

    if include_expenditures:
        summary_columns.extend(
            [
                Column(
                    name=ExpenditureType.DAY_MEAL.value,
                    label="Repas midi",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name=ExpenditureType.NIGHT_MEAL.value,
                    label="Repas soir",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name=ExpenditureType.SLEEP_OVER.value,
                    label="Découché",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name=ExpenditureType.SNACK.value,
                    label="Casse-croûte",
                    color="#FFE5B9",
                    secondary=True,
                ),
            ]
        )

    return summary_columns


def _get_detail_columns(
    include_support=False, include_expenditures=False, include_transfers=False
):
    columns = [
        Column(
            name="start_time",
            label="Début",
            color="#CFDAC8",
            secondary=True,
        ),
        Column(
            name="end_time",
            label="Fin",
            color="#CFDAC8",
            secondary=True,
        ),
        Column(
            name="service",
            label="Amplitude",
            color="#CFDAC8",
            format=format_seconds_duration,
            right_border=True,
        ),
        Column(
            name=ActivityType.DRIVE.value,
            label="Conduite",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
        Column(
            name=ActivityType.WORK.value,
            label="Autre tâche",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
    ]

    if include_transfers:
        columns.append(
            Column(
                name=ActivityType.TRANSFER.value,
                label="Temps de Liaison",
                color="#C9CBFF",
                secondary=True,
                format=format_seconds_duration,
            )
        )

    if include_support:
        columns.append(
            Column(
                name=ActivityType.SUPPORT.value,
                label="Accompagnement",
                color="#C9CBFF",
                secondary=True,
                format=format_seconds_duration,
            )
        )

    columns.extend(
        [
            Column(
                name="break",
                label="Pause",
                color="#C9CBFF",
                secondary=True,
                format=format_seconds_duration,
            ),
            Column(
                name="total_work",
                label="Heures travaillées",
                color="#C9CBFF",
                format=format_seconds_duration,
            ),
            Column(
                name="night_hours",
                label="Dont heures au tarif nuit",
                color="#C9CBFF",
                format=format_seconds_duration,
                secondary=True,
                right_border=True,
            ),
        ]
    )

    if include_expenditures:
        columns.extend(
            [
                Column(
                    name=ExpenditureType.DAY_MEAL.value,
                    label="Repas midi",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name=ExpenditureType.NIGHT_MEAL.value,
                    label="Repas soir",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name=ExpenditureType.SLEEP_OVER.value,
                    label="Découché",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name=ExpenditureType.SNACK.value,
                    label="Casse-croûte",
                    color="#FFE5B9",
                    secondary=True,
                ),
            ]
        )

    return columns


def _generate_work_days_pdf(
    user,
    work_days,
    start_date,
    end_date,
    include_support_activity=False,
    include_expenditures=False,
    include_transfers=False,
):
    months = []
    weeks = []

    current_month = start_date.replace(day=1)
    last_month = end_date.replace(day=1)
    while current_month <= last_month:
        months.append(
            {
                "date": current_month,
                "worked_days": 0,
                ActivityType.DRIVE.value: 0,
                ActivityType.WORK.value: 0,
                ActivityType.SUPPORT.value: 0,
                ActivityType.TRANSFER.value: 0,
                "total_work": 0,
                ExpenditureType.DAY_MEAL.value: 0,
                ExpenditureType.NIGHT_MEAL.value: 0,
                ExpenditureType.SLEEP_OVER.value: 0,
                ExpenditureType.SNACK.value: 0,
            }
        )
        current_month += relativedelta(months=1)

    current_week = start_date - timedelta(days=start_date.weekday())
    last_week = end_date - timedelta(days=end_date.weekday())
    while current_week <= last_week:
        weeks.append(
            {
                "start": current_week,
                "end": current_week + timedelta(days=6),
                "worked_days": 0,
                ActivityType.DRIVE.value: 0,
                ActivityType.WORK.value: 0,
                ActivityType.SUPPORT.value: 0,
                ActivityType.TRANSFER.value: 0,
                "total_work": 0,
                "night_hours": 0,
                ExpenditureType.DAY_MEAL.value: 0,
                ExpenditureType.NIGHT_MEAL.value: 0,
                ExpenditureType.SLEEP_OVER.value: 0,
                ExpenditureType.SNACK.value: 0,
                "days": [],
            }
        )
        current_week += timedelta(days=7)

    total = {
        "worked_days": 0,
        ActivityType.DRIVE.value: 0,
        ActivityType.WORK.value: 0,
        ActivityType.SUPPORT.value: 0,
        ActivityType.TRANSFER.value: 0,
        "total_work": 0,
        ExpenditureType.DAY_MEAL.value: 0,
        ExpenditureType.NIGHT_MEAL.value: 0,
        ExpenditureType.SLEEP_OVER.value: 0,
        ExpenditureType.SNACK.value: 0,
    }

    for wd in work_days:
        month = [m for m in months if m["date"] == wd.day.replace(day=1)][0]
        week = [
            w
            for w in weeks
            if w["start"] == wd.day - timedelta(days=wd.day.weekday())
        ][0]

        for accumulator in [month, week, total]:
            accumulator["worked_days"] += 1

            accumulator["total_work"] += wd.total_work_duration
            if "night_hours" in accumulator:
                accumulator[
                    "night_hours"
                ] += wd.total_night_work_tarification_duration

            for type_ in ActivityType:
                accumulator[type_.value] += wd.activity_durations[type_]

            for type_ in ExpenditureType:
                accumulator[type_.value] += wd.expenditures.get(type_, 0)

        show_not_validated_by_self_alert = any(
            [m.validation_of(user) is None for m in wd.missions]
        )
        show_not_validated_by_admin_alert = (
            not show_not_validated_by_self_alert
        ) and any([not m.validated_by_admin_for(user) for m in wd.missions])
        show_modifications_after_validation_alert = (
            not show_not_validated_by_self_alert
        ) and any(
            [
                m.modification_status_and_latest_action_time_for_user(user)[0]
                in [
                    UserMissionModificationStatus.OTHERS_MODIFIED_AFTER_USER,
                    UserMissionModificationStatus.ONLY_OTHERS_ACTIONS,
                ]
                for m in wd.missions
            ]
        )

        week["days"].append(
            {
                "date": wd.day,
                "start_time": "-"
                if wd.is_first_mission_overlapping_with_previous_day
                else format_time(wd.start_time, False),
                "end_time": "-"
                if wd.is_last_mission_overlapping_with_next_day
                else format_time(wd.end_time or wd.end_of_day, False),
                "service": wd.service_duration,
                "total_work": wd.total_work_duration,
                **{
                    type_.value: wd.activity_durations[type_]
                    for type_ in ActivityType
                },
                **{
                    type_.value: wd.expenditures.get(type_, 0)
                    for type_ in ExpenditureType
                },
                "night_hours": wd.total_night_work_tarification_duration,
                "not_validated_by_self": show_not_validated_by_self_alert,
                "not_validated_by_admin": show_not_validated_by_admin_alert,
                "modified_after_self_validation": show_modifications_after_validation_alert,
            }
        )

    current_group_count = 0
    current_group_uses_extra_space = start_date.weekday() == 0
    for week in weeks:
        week["start"] = max(week["start"], start_date)
        week["end"] = min(week["end"], end_date)
        week.update(
            {
                "has_day_not_validated_by_self": any(
                    [d["not_validated_by_self"] for d in week["days"]]
                ),
                "has_day_not_validated_by_admin": any(
                    [d["not_validated_by_admin"] for d in week["days"]]
                ),
                "has_day_modified_after_self_validation": any(
                    [d["modified_after_self_validation"] for d in week["days"]]
                ),
            }
        )
        days_with_works = [d["date"] for d in week["days"]]
        current_day = week["start"]
        while current_day <= week["end"]:
            if (
                start_date <= current_day <= end_date
                and current_day not in days_with_works
            ):
                week["days"].append({"date": current_day, "is_empty": True})
            current_day += timedelta(days=1)

        for d in week["days"]:
            d["is_sunday_or_bank_holiday"] = is_sunday_or_bank_holiday(
                d["date"]
            )

        week["days"].sort(key=lambda d: d["date"])
        current_group_count += 1
        if current_group_count == (3 if current_group_uses_extra_space else 4):
            week["break_after"] = True
            current_group_count = 0
            current_group_uses_extra_space = False

    has_any_week_comment_not_validated_by_self = any(
        [w["has_day_not_validated_by_self"] for w in weeks]
    )
    has_any_week_comment_not_validated_by_admin = any(
        [w["has_day_not_validated_by_admin"] for w in weeks]
    )
    has_any_week_comment_modified_after_self_validation = any(
        [w["has_day_modified_after_self_validation"] for w in weeks]
    )

    return generate_pdf_from_template(
        "work_days_pdf.html",
        user_name=user.display_name,
        start_date=start_date,
        end_date=end_date,
        summary_columns=_get_summary_columns(
            include_support=include_support_activity
            or total[ActivityType.SUPPORT] > 0,
            include_expenditures=include_expenditures,
        ),
        day_columns=_get_detail_columns(
            include_support=include_support_activity
            or total[ActivityType.SUPPORT] > 0,
            include_expenditures=include_expenditures,
            include_transfers=include_transfers
            or total[ActivityType.TRANSFER] > 0,
        ),
        weeks=weeks,
        has_any_week_comment_not_validated_by_self=has_any_week_comment_not_validated_by_self,
        has_any_week_comment_not_validated_by_admin=has_any_week_comment_not_validated_by_admin,
        has_any_week_comment_modified_after_self_validation=has_any_week_comment_modified_after_self_validation,
        months=months,
        total=total,
        show_month_total=len(months) > 1,
        show_week_summary=True,
        break_after_month=len(months) > 2,
        generation_time=datetime.now(),
    )


def generate_work_days_pdf_for(
    user,
    start_date,
    end_date,
    include_support_activity=False,
    include_expenditures=False,
    include_transfers=False,
):
    work_days, _ = group_user_events_by_day_with_limit(
        user, from_date=start_date, until_date=end_date
    )
    return _generate_work_days_pdf(
        user,
        work_days,
        start_date,
        end_date,
        include_support_activity=include_support_activity,
        include_expenditures=include_expenditures,
        include_transfers=include_transfers,
    )
