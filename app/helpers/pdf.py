from typing import NamedTuple
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from xhtml2pdf import pisa
from flask import render_template
from io import BytesIO

from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.time import to_fr_tz
from app.models.activity import ActivityType
from app.models.expenditure import ExpenditureType
from app.models.mission import UserMissionModificationStatus
from app.templates.filters import format_seconds_duration, format_time


class Column(NamedTuple):
    name: str
    label: str
    color: str
    format: any = lambda x: x
    secondary: bool = False
    number: bool = True


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


def _get_detail_columns(include_support=False, include_expenditures=False):
    columns = [
        Column(
            name="start_time",
            label="Début",
            color="#CFDAC8",
            secondary=True,
            format=lambda x: format_time(x, False),
        ),
        Column(
            name="end_time",
            label="Fin",
            color="#CFDAC8",
            secondary=True,
            format=lambda x: format_time(x, False),
        ),
        Column(
            name="service",
            label="Amplitude",
            color="#CFDAC8",
            format=format_seconds_duration,
        ),
        Column(
            name="drive",
            label="Conduite",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
        Column(
            name="work",
            label="Autre tâche",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
    ]

    if include_support:
        columns.append(
            Column(
                name="support",
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
        ]
    )

    if include_expenditures:
        columns.extend(
            [
                Column(
                    name="day_meal",
                    label="Repas midi",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name="night_meal",
                    label="Repas soir",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name="sleep_over",
                    label="Découché",
                    color="#FFE5B9",
                    secondary=True,
                ),
                Column(
                    name="snack",
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
                "drive": 0,
                "work": 0,
                "support": 0,
                "total_work": 0,
                "day_meal": 0,
                "night_meal": 0,
                "sleep_over": 0,
                "snack": 0,
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
                "drive": 0,
                "work": 0,
                "support": 0,
                "total_work": 0,
                "day_meal": 0,
                "night_meal": 0,
                "sleep_over": 0,
                "snack": 0,
                "days": [],
            }
        )
        current_week += timedelta(days=7)

    total = {
        "worked_days": 0,
        "drive": 0,
        "work": 0,
        "support": 0,
        "total_work": 0,
        "day_meal": 0,
        "night_meal": 0,
        "sleep_over": 0,
        "snack": 0,
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

            for type_ in ActivityType:
                accumulator[type_.value] += wd.activity_durations[type_]

            for type_ in ExpenditureType:
                accumulator[type_.value] += wd.expenditures.get(type_, 0)

        show_not_validated_by_self_alert = any(
            [m.latest_validation_time_of(user) is None for m in wd.missions]
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
                "start_time": to_fr_tz(wd.start_time),
                "end_time": to_fr_tz(wd.end_time or wd.end_of_day),
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
                week["days"].append({"date": current_day})
            current_day += timedelta(days=1)

        week["days"].sort(key=lambda d: d["date"])
        current_group_count += 1
        if (
            week["has_day_not_validated_by_self"]
            or week["has_day_not_validated_by_admin"]
            or week["has_day_modified_after_self_validation"]
        ):
            current_group_uses_extra_space = True
        if current_group_count == (3 if current_group_uses_extra_space else 4):
            week["break_after"] = True
            current_group_count = 0
            current_group_uses_extra_space = False

    html = render_template(
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
        ),
        weeks=weeks,
        months=months,
        total=total,
        show_month_total=len(months) > 1,
        show_week_summary=True,
        break_after_month=len(months) > 2,
        generation_time=datetime.now(),
    )

    output = BytesIO()
    pisa.CreatePDF(html, output)
    output.seek(0)

    return output


def generate_work_days_pdf_for(
    user,
    start_date,
    end_date,
    include_support_activity=False,
    include_expenditures=False,
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
    )
