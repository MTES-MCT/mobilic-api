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
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h{minutes if minutes >= 10 else '0' + str(minutes)}"


def format_day(day):
    return day.strftime("%d/%m")


def pretty_format_day(day):
    return f"{DAYS[day.weekday()]} {day.strftime('%d/%m')}"


def pretty_format_month(month_start):
    return f"{MONTHS[month_start.month - 1]} {month_start.year}"


def full_format_day(day):
    return day.strftime("%d/%m/%Y")


JINJA_CUSTOM_FILTERS = {
    "format_time": format_time,
    "format_duration": format_seconds_duration,
    "format_day": format_day,
    "pretty_format_day": pretty_format_day,
    "pretty_format_month": pretty_format_month,
    "full_format_day": full_format_day,
}
