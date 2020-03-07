from collections import defaultdict
from flask import send_file
from xlsxwriter import Workbook
from datetime import timedelta
from io import BytesIO

from app.models.activity import ActivityTypes
from app.models.expenditure import ExpenditureTypes


ACTIVITY_TYPE_LABEL = {
    ActivityTypes.DRIVE: "conduite",
    ActivityTypes.WORK: "autre tâche",
    ActivityTypes.BREAK: "pause",
    ActivityTypes.SUPPORT: "accompagnement",
    ActivityTypes.REST: "repos",
}

EXCEL_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


columns_in_main_sheet = [
    ("Employé", lambda wday: wday.user.display_name, None),
    ("Jour", lambda wday: wday.start_time, "date_format"),
    ("Véhicule", lambda wday: wday.vehicle_registration_number, None),
    ("Mission", lambda wday: wday.mission, None),
    ("Début", lambda wday: wday.start_time, "time_format"),
    ("Fin", lambda wday: wday.end_time, "time_format"),
    (
        "Conduite",
        lambda wday: timedelta(
            milliseconds=wday.activity_timers[ActivityTypes.DRIVE]
        ),
        "duration_format",
    ),
    (
        "Accompagnement",
        lambda wday: timedelta(
            milliseconds=wday.activity_timers[ActivityTypes.SUPPORT]
        ),
        "duration_format",
    ),
    (
        "Autre tâche",
        lambda wday: timedelta(
            milliseconds=wday.activity_timers[ActivityTypes.WORK]
        ),
        "duration_format",
    ),
    (
        "Pause",
        lambda wday: timedelta(
            milliseconds=wday.activity_timers[ActivityTypes.BREAK]
        ),
        "duration_format",
    ),
    (
        "Repas jour",
        lambda wday: len(
            [
                e
                for e in wday.expenditures
                if e.type == ExpenditureTypes.DAY_MEAL
            ]
        ),
        None,
    ),
    (
        "Repas nuit",
        lambda wday: len(
            [
                e
                for e in wday.expenditures
                if e.type == ExpenditureTypes.NIGHT_MEAL
            ]
        ),
        None,
    ),
    (
        "Découchage",
        lambda wday: len(
            [
                e
                for e in wday.expenditures
                if e.type == ExpenditureTypes.SLEEP_OVER
            ]
        ),
        None,
    ),
    (
        "Commentaires",
        lambda wday: "\n".join([" - " + c.content for c in wday.comments]),
        None,
    ),
]

columns_in_user_sheet = [
    ("Activité", lambda activity: ACTIVITY_TYPE_LABEL[activity.type], None),
    ("Jour", lambda activity: activity.start_time, "date_format"),
    ("Heure", lambda activity: activity.start_time, "time_format"),
    ("Saisi par", lambda activity: activity.submitter.display_name, None),
]


def send_work_days_as_excel(user_wdays):
    complete_work_days = [wd for wd in user_wdays if wd.is_complete]
    output = BytesIO()
    wb = Workbook(output)

    date_formats = dict(
        date_format=wb.add_format({"num_format": "dd/mm/yyyy"}),
        time_format=wb.add_format({"num_format": "h:mm"}),
        duration_format=wb.add_format({"num_format": "[h]:mm"}),
    )
    formats = dict(bold=wb.add_format({"bold": True}), **date_formats)

    wdays_by_user = defaultdict(list)
    for work_day in complete_work_days:
        wdays_by_user[work_day.user].append(work_day)

    main_sheet = wb.add_worksheet("Global")
    main_row_idx = 1

    main_col_idx = 0
    for (main_col_name, resolver, _) in columns_in_main_sheet:
        main_sheet.write(0, main_col_idx, main_col_name, formats["bold"])
        main_col_idx += 1

    user_idx = 1
    for user, work_days in wdays_by_user.items():
        activities = [a for wday in work_days for a in wday.activities]
        activities.sort(key=lambda a: a.start_time)
        user_sheet = wb.add_worksheet(user.display_name + f" ({user_idx})")
        col_idx = 0
        for (col_name, resolver, style) in columns_in_user_sheet:
            user_sheet.write(0, col_idx, col_name, formats["bold"])
            row_idx = 1
            for act in activities:
                if style in date_formats:
                    user_sheet.write_datetime(
                        row_idx, col_idx, resolver(act), formats.get(style)
                    )
                else:
                    user_sheet.write(
                        row_idx, col_idx, resolver(act), formats.get(style)
                    )
                row_idx += 1
            col_idx += 1

        for wday in sorted(work_days, key=lambda wd: wd.start_time):
            main_col_idx = 0
            for (main_col_name, resolver, style) in columns_in_main_sheet:
                if style in date_formats:
                    main_sheet.write_datetime(
                        main_row_idx,
                        main_col_idx,
                        resolver(wday),
                        formats.get(style),
                    )
                else:
                    main_sheet.write(
                        main_row_idx,
                        main_col_idx,
                        resolver(wday),
                        formats.get(style),
                    )
                main_col_idx += 1
            main_row_idx += 1

        user_idx += 1

    wb.close()

    output.seek(0)

    return send_file(
        output,
        mimetype=EXCEL_MIMETYPE,
        as_attachment=True,
        attachment_filename="temps_de_travail.xlsx",
    )
