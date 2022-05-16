from app.helpers.time import to_fr_tz
from app.helpers.xls.common import (
    write_sheet_header,
    light_grey_hex,
    light_yellow_hex,
    light_blue_hex,
    light_green_hex,
    light_red_hex,
    formats,
    write_tab_headers,
    write_cells,
    merge_cells_if_needed,
)
from app.models.activity import Activity
from app.templates.filters import format_activity_type


def write_day_details_sheet(
    wb, wdays_by_user, require_mission_name, companies, min_date, max_date
):
    sheet = wb.add_worksheet("Détail")
    sheet.protect()
    sheet.freeze_panes(3, 2)
    write_sheet_header(wb, sheet, companies, max_date, min_date)

    all_columns = [
        *workday_columns,
        *get_mission_columns(require_mission_name),
        *event_columns,
    ]

    row_idx = 3

    for user, work_days in sorted(
        wdays_by_user.items(), key=lambda u: u[0].display_name
    ):
        column_base_formats = write_tab_headers(
            wb, sheet, row_idx, all_columns
        )
        row_idx += 1
        user_starting_row_idx = row_idx
        col_idx = 0
        for wday in sorted(work_days, key=lambda wd: wd.day):
            workday_starting_row_idx = row_idx
            for mission in sorted(
                wday.missions, key=lambda mi: mi.creation_time
            ):
                first_activities_for_user = next(
                    iter(mission.activities_for(user)), None
                )
                mission_starting_row_idx = row_idx
                if (
                    first_activities_for_user
                    and first_activities_for_user.start_time.date() == wday.day
                ):
                    for history_event in sorted(
                        mission.history, key=lambda ev: ev.time
                    ):
                        col_idx = 0
                        additional_format = (
                            {"top": 1}
                            if mission_starting_row_idx == row_idx
                            else None
                        )
                        col_idx = write_cells(
                            wb,
                            sheet,
                            column_base_formats,
                            col_idx,
                            row_idx,
                            workday_columns,
                            wday,
                        )
                        col_idx = write_cells(
                            wb,
                            sheet,
                            column_base_formats,
                            col_idx,
                            row_idx,
                            get_mission_columns(require_mission_name),
                            mission,
                        )
                        col_idx = write_cells(
                            wb,
                            sheet,
                            column_base_formats,
                            col_idx,
                            row_idx,
                            event_columns,
                            history_event,
                            additional_format,
                        )
                        row_idx += 1
                merge_cells_if_needed(
                    wb,
                    sheet,
                    mission_starting_row_idx,
                    row_idx,
                    2,
                    mission.name,
                    formats.get("merged_center"),
                )

            merge_cells_if_needed(
                wb,
                sheet,
                workday_starting_row_idx,
                row_idx,
                1,
                to_fr_tz(wday.start_time),
                formats.get("merged_date_format"),
            )
        merge_cells_if_needed(
            wb,
            sheet,
            user_starting_row_idx,
            row_idx,
            0,
            wday.user.display_name,
            formats.get("merged_top"),
        )
        for col_to_format in range(col_idx):
            sheet.write(
                row_idx,
                col_to_format,
                "",
                wb.add_format({"top": 1}),
            )

        row_idx += 2


workday_columns = [
    (
        "Employé",
        lambda wday: wday.user.display_name,
        "bold",
        30,
        light_grey_hex,
    ),
    (
        "Jour",
        lambda a: to_fr_tz(a.start_time),
        "date_format",
        20,
        light_yellow_hex,
    ),
]


def get_mission_columns(require_mission_name):
    mission_columns = []
    if require_mission_name:
        mission_columns.extend(
            [
                (
                    "Mission",
                    lambda mission: mission.name,
                    None,
                    20,
                    light_blue_hex,
                )
            ]
        )
    return mission_columns


event_columns = [
    (
        "Date et heure de l'enregistrement",
        lambda event: to_fr_tz(event.time),
        "date_and_time_format",
        20,
        light_green_hex,
    ),
    (
        "Auteur de l'enregistrement",
        lambda event: event.submitter.display_name,
        "center",
        30,
        light_green_hex,
    ),
    (
        "Statut de l'auteur",
        lambda event: "Administrateur"
        if event.submitter_has_admin_rights
        else "Travailleur mobile",
        "center",
        30,
        light_green_hex,
    ),
    (
        "Description de l'enregistrement",
        lambda event: event.text(False),
        None,
        60,
        light_green_hex,
    ),
    (
        "Activités effectuées",
        lambda event: format_activity_type(event.resource.type)
        if type(event.resource) is Activity
        else None,
        None,
        15,
        light_blue_hex,
    ),
    (
        "Observations",
        lambda event: event.version.context.get("userComment")
        if event.version and event.version.context
        else None,
        "wrap",
        60,
        light_red_hex,
    ),
]
