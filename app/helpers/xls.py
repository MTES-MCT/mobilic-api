from collections import defaultdict
from flask import send_file
from xlsxwriter import Workbook
from datetime import timedelta
from io import BytesIO

from app.models.activity import ActivityType


ACTIVITY_TYPE_LABEL = {
    ActivityType.DRIVE: "conduite",
    ActivityType.WORK: "autre tâche",
    ActivityType.SUPPORT: "accompagnement",
}

EXCEL_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


columns_in_main_sheet = [
    ("Employé", lambda wday: wday.user.display_name, None, 30),
    ("Jour", lambda wday: wday.start_time, "date_format", 20),
    ("Début", lambda wday: wday.start_time, "time_format", 15),
    ("Fin", lambda wday: wday.end_time, "time_format", 15),
    (
        "Conduite",
        lambda wday: timedelta(
            seconds=wday.activity_timers[ActivityType.DRIVE]
        ),
        "duration_format",
        10,
    ),
    (
        "Accompagnement",
        lambda wday: timedelta(
            seconds=wday.activity_timers[ActivityType.SUPPORT]
        ),
        "duration_format",
        10,
    ),
    (
        "Autre tâche",
        lambda wday: timedelta(
            seconds=wday.activity_timers[ActivityType.WORK]
        ),
        "duration_format",
        10,
    ),
    (
        "Pause",
        lambda wday: timedelta(seconds=wday.activity_timers["break"]),
        "duration_format",
        10,
    ),
    (
        "Repas jour",
        lambda wday: wday.expenditures.get("day_meal", 0),
        None,
        10,
    ),
    (
        "Repas nuit",
        lambda wday: wday.expenditures.get("night_meal", 0),
        None,
        10,
    ),
    (
        "Découchage",
        lambda wday: wday.expenditures.get("sleep_over", 0),
        None,
        10,
    ),
    (
        "Casse-croûte",
        lambda wday: wday.expenditures.get("snack", 0),
        None,
        10,
    ),
    (
        "Mission(s)",
        lambda wday: ", ".join([m.name for m in wday.missions if m.name]),
        None,
        30,
    ),
    (
        "Entreprise(s)",
        lambda wday: ", ".join([c.name for c in wday.companies if c.name]),
        None,
        30,
    ),
    (
        "Commentaires",
        lambda wday: "\n".join([" - " + c for c in wday.activity_comments]),
        None,
        50,
    ),
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

    main_sheet = wb.add_worksheet("Activité")
    main_row_idx = 1

    main_col_idx = 0
    for (main_col_name, resolver, _, column_width) in columns_in_main_sheet:
        main_sheet.write(0, main_col_idx, main_col_name, formats["bold"])
        main_sheet.set_column(main_col_idx, main_col_idx, column_width)
        main_col_idx += 1

    for user, work_days in wdays_by_user.items():
        for wday in sorted(work_days, key=lambda wd: wd.start_time):
            main_col_idx = 0
            for (main_col_name, resolver, style, _) in columns_in_main_sheet:
                if style in date_formats and resolver(wday) is not None:
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

    wb.close()

    output.seek(0)

    return send_file(
        output,
        mimetype=EXCEL_MIMETYPE,
        as_attachment=True,
        attachment_filename="rapport_activité.xlsx",
    )
