from collections import namedtuple
from datetime import timedelta

from app.domain.history import LogActionType
from app.helpers.time import is_sunday_or_bank_holiday, to_fr_tz
from app.helpers.xls.common import (
    light_grey_hex,
    light_yellow_hex,
    light_blue_hex,
    light_green_hex,
    light_orange_hex,
    light_red_hex,
)
from app.models.activity import ActivityType, Activity
from app.templates.filters import format_activity_type

ExcelColumn = namedtuple(
    "ExcelColumn",
    [
        "label",
        "lambda_value",
        "lambda_style",
        "width",
        "color",
        "is_to_be_summed",
    ],
    defaults=("", lambda _: "", lambda _: "", 20, light_grey_hex, False),
)

COLUMN_ENTREPRISE = ExcelColumn(
    "Entreprise",
    lambda wday: ", ".join(
        set([m.company.name for m in wday.missions if m.company is not None])
    ),
    lambda _: "bold",
    30,
    light_grey_hex,
    False,
)
COLUMN_SIREN = ExcelColumn(
    "SIREN",
    lambda wday: ", ".join(
        set([m.company.siren for m in wday.missions if m.company is not None])
    ),
    lambda _: "bold",
    30,
    light_grey_hex,
    False,
)
COLUMN_EMPLOYEE = ExcelColumn(
    "Employé",
    lambda wday: wday.user.display_name,
    lambda _: "bold",
    30,
    light_grey_hex,
    False,
)
COLUMN_DAY = ExcelColumn(
    "Jour",
    lambda wday: wday.day,
    lambda wday: "bank_holiday_date_format"
    if is_sunday_or_bank_holiday(wday.day)
    else "date_format",
    20,
    light_yellow_hex,
    False,
)
COLUMN_DETAILS_DAY = ExcelColumn(
    "Jour",
    lambda a: to_fr_tz(a.start_time),
    lambda _: "date_format",
    20,
    light_yellow_hex,
)
COLUMN_MISSIONS = ExcelColumn(
    "Mission(s)",
    lambda wday: ", ".join([m.name for m in wday.missions if m.name]),
    lambda _: "wrap",
    30,
    light_blue_hex,
    False,
)
COLUMN_MISSION = ExcelColumn(
    "Mission",
    lambda mission: mission.name,
    lambda _: None,
    20,
    light_blue_hex,
)
COLUMN_VEHICLES = ExcelColumn(
    "Véhicule(s)",
    lambda wday: ", ".join(
        set([m.vehicle.name for m in wday.missions if m.vehicle is not None])
    ),
    lambda _: "wrap",
    30,
    light_blue_hex,
    False,
)
COLUMN_START = ExcelColumn(
    "Début",
    lambda wday: "-"
    if wday.is_first_mission_overlapping_with_previous_day
    else to_fr_tz(wday.start_time)
    if wday.start_time
    else None,
    lambda wday: "time_format"
    if not wday.is_first_mission_overlapping_with_previous_day
    else "center",
    15,
    light_green_hex,
    False,
)
COLUMN_END = ExcelColumn(
    "Fin",
    lambda wday: "-"
    if wday.is_last_mission_overlapping_with_next_day
    else to_fr_tz(wday.end_time)
    if wday.end_time
    else None,
    lambda wday: "time_format"
    if not wday.is_last_mission_overlapping_with_next_day
    else "center",
    15,
    light_green_hex,
    False,
)
COLUMN_DRIVE = ExcelColumn(
    "Conduite",
    lambda wday: timedelta(
        seconds=wday.activity_durations[ActivityType.DRIVE]
    ),
    lambda _: "duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_SUPPORT = ExcelColumn(
    "Accompagnement",
    lambda wday: timedelta(
        seconds=wday.activity_durations[ActivityType.SUPPORT]
    ),
    lambda _: "duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_OTHER_TASK = ExcelColumn(
    "Autre tâche",
    lambda wday: timedelta(seconds=wday.activity_durations[ActivityType.WORK]),
    lambda _: "duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_TOTAL_WORK = ExcelColumn(
    "Total travail",
    lambda wday: timedelta(seconds=wday.total_work_duration),
    lambda wday: "bank_holiday_duration_format"
    if wday and is_sunday_or_bank_holiday(wday.day)
    else "bold_duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_NIGHTLY_HOURS = ExcelColumn(
    "Heures au tarif nuit",
    lambda wday: timedelta(
        seconds=wday.total_night_work_tarification_duration
    ),
    lambda _: "duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_TRANSFER = ExcelColumn(
    "Liaison",
    lambda wday: timedelta(
        seconds=wday.activity_durations[ActivityType.TRANSFER]
    ),
    lambda _: "duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_BREAK = ExcelColumn(
    "Pause",
    lambda wday: timedelta(
        seconds=wday.service_duration
        - wday.total_work_duration
        - wday.activity_durations[ActivityType.TRANSFER]
    ),
    lambda _: "duration_format",
    13,
    light_green_hex,
    True,
)
COLUMN_AMPLITUDE = ExcelColumn(
    "Amplitude",
    lambda wday: timedelta(seconds=wday.service_duration),
    lambda _: "duration_format",
    13,
    light_green_hex,
    False,
)
COLUMN_START_LOCATION = ExcelColumn(
    "Lieu de début de service",
    lambda wday: wday.start_location.address.format()
    if wday.start_location
    else "",
    lambda _: "wrap",
    30,
    light_blue_hex,
    False,
)
COLUMN_END_LOCATION = ExcelColumn(
    "Lieu de fin de service",
    lambda wday: wday.end_location.address.format()
    if wday.end_location
    else "",
    lambda _: "wrap",
    30,
    light_blue_hex,
    False,
)
COLUMN_START_KM = ExcelColumn(
    "Relevé km de début de service (si même véhicule utilisé au cours de la journée)",
    lambda wday: format_kilometer_reading(wday.start_location, wday),
    lambda _: "center",
    30,
    light_blue_hex,
    False,
)
COLUMN_END_KM = ExcelColumn(
    "Relevé km de fin de service (si même véhicule utilisé au cours de la journée)",
    lambda wday: format_kilometer_reading(wday.end_location, wday),
    lambda _: "center",
    30,
    light_blue_hex,
    False,
)
COLUMN_TOTAL_KM = ExcelColumn(
    "Nombre de kilomètres parcourus",
    lambda wday: format_kilometer_driven_in_wday(wday),
    lambda _: "center",
    30,
    light_blue_hex,
    True,
)
COLUMN_EXPENDITURE_DAY_MEAL = ExcelColumn(
    "Repas midi",
    lambda wday: wday.expenditures.get("day_meal", 0),
    lambda _: "center",
    13,
    light_orange_hex,
    True,
)
COLUMN_EXPENDITURE_NIGHT_MEAL = ExcelColumn(
    "Repas soir",
    lambda wday: wday.expenditures.get("night_meal", 0),
    lambda _: "center",
    13,
    light_orange_hex,
    True,
)
COLUMN_EXPENDITURE_SLEEP_OVER = ExcelColumn(
    "Découché",
    lambda wday: wday.expenditures.get("sleep_over", 0),
    lambda _: "center",
    13,
    light_orange_hex,
    True,
)
COLUMN_EXPENDITURE_SNACK = ExcelColumn(
    "Casse-croûte",
    lambda wday: wday.expenditures.get("snack", 0),
    lambda _: "center",
    13,
    light_orange_hex,
    True,
)
COLUMN_OBSERVATIONS = ExcelColumn(
    "Observations",
    lambda wday: "\n".join([" - " + c.text for c in wday.comments]),
    lambda _: "wrap",
    50,
    light_red_hex,
    False,
)
COLUMN_EVENT_TIME = ExcelColumn(
    "Date et heure de l'enregistrement",
    lambda event: to_fr_tz(event.time),
    lambda _: "date_and_time_format",
    20,
    light_green_hex,
)
COLUMN_EVENT_AUTHOR = ExcelColumn(
    "Auteur de l'enregistrement",
    lambda event: event.submitter.display_name,
    lambda _: "center",
    30,
    light_green_hex,
)
COLUMN_EVENT_AUTHOR_STATUS = ExcelColumn(
    "Statut de l'auteur",
    lambda event: "Administrateur"
    if event.submitter_has_admin_rights
    else "Travailleur mobile",
    lambda _: "center",
    30,
    light_green_hex,
)
COLUMN_EVENT_DESC = ExcelColumn(
    "Description de l'enregistrement",
    lambda event: event.text,
    lambda _: None,
    60,
    light_green_hex,
)
COLUMN_EVENT_ACTIVITIES = ExcelColumn(
    "Activités effectuées",
    lambda event: format_activity_type(event.resource.type)
    if type(event.resource) is Activity
    and event.type == LogActionType.CREATE
    and not event.resource.dismissed_at
    else None,
    lambda _: None,
    15,
    light_blue_hex,
)
COLUMN_EVENT_OBSERVATIONS = ExcelColumn(
    "Observations",
    lambda event: event.version.context.get("userComment")
    if event.version and event.version.context
    else None,
    lambda _: "wrap",
    60,
    light_red_hex,
)


def format_kilometer_reading(location, wday):
    if (
        not wday.one_and_only_one_vehicle_used
        or not location
        or not location.kilometer_reading
    ):
        return ""
    return location.kilometer_reading


def format_kilometer_driven_in_wday(wday):
    if (
        not wday.one_and_only_one_vehicle_used
        or not wday.start_location
        or not wday.end_location
        or not wday.start_location.kilometer_reading
        or not wday.end_location.kilometer_reading
    ):
        return ""
    return (
        wday.end_location.kilometer_reading
        - wday.start_location.kilometer_reading
    )
