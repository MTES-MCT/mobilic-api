from datetime import timedelta

DAYS = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]

MONTHS = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def format_time(value, show_dates):
    if show_dates:
        return value.strftime("%d/%m/%y %H:%M")
    return value.strftime("%H:%M")


def format_seconds_duration(seconds):
    _seconds = seconds
    if type(seconds) is timedelta:
        _seconds = int(seconds.total_seconds())
    hours = _seconds // 3600
    minutes = (_seconds % 3600) // 60
    return f"{hours}h{minutes if minutes >= 10 else '0' + str(minutes)}"


def format_day(day):
    return day.strftime("%d/%m")


def pretty_format_day(day):
    return f"{DAYS[day.weekday()]} {day.strftime('%d/%m')}"


def pretty_format_month(month_start):
    return f"{MONTHS[month_start.month - 1]} {month_start.year}"


def full_format_day(day):
    return day.strftime("%d/%m/%Y")


def format_activity_type(activity_or_break_type):
    from app.models.activity import ActivityType

    if activity_or_break_type == ActivityType.WORK:
        return "autre tâche"
    if activity_or_break_type == ActivityType.DRIVE:
        return "conduite"
    if activity_or_break_type == ActivityType.SUPPORT:
        return "accompagnement"
    return "pause"


def format_expenditure_label(expenditure_type):
    from app.models.expenditure import ExpenditureType

    if expenditure_type == ExpenditureType.SNACK:
        return "casse-croûte(s)"
    if expenditure_type == ExpenditureType.DAY_MEAL:
        return "repas midi"
    if expenditure_type == ExpenditureType.NIGHT_MEAL:
        return "repas soir"
    if expenditure_type == ExpenditureType.SLEEP_OVER:
        return "découché(s)"


def format_expenditures_string_from_count(expenditures_count):
    return ", ".join(
        [
            f"{count} {format_expenditure_label(exp_type)}"
            for exp_type, count in expenditures_count.items()
        ]
    )


JINJA_CUSTOM_FILTERS = {
    "format_time": format_time,
    "format_duration": format_seconds_duration,
    "format_day": format_day,
    "pretty_format_day": pretty_format_day,
    "pretty_format_month": pretty_format_month,
    "full_format_day": full_format_day,
    "format_activity_type": format_activity_type,
}
