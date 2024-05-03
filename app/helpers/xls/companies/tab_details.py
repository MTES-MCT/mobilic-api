from app.helpers.xls.columns import *
from app.helpers.xls.common import (
    formats,
    write_tab_headers,
    write_cells,
    merge_cells_if_needed,
    red_hex,
)
from app.helpers.xls.companies.headers import write_sheet_header


def write_day_details_sheet(
    wb,
    wdays_by_user,
    require_mission_name,
    companies,
    min_date,
    max_date,
    deleted_missions=False,
):
    if deleted_missions:
        sheet = wb.add_worksheet("Missions supprimées")
        all_columns = [
            *deleted_workday_columns,
            *get_mission_columns(require_mission_name),
            *event_columns,
        ]
    else:
        sheet = wb.add_worksheet("Détail")
        all_columns = [
            *workday_columns,
            *get_mission_columns(require_mission_name),
            *event_columns,
        ]
    sheet.protect()

    row_idx = write_sheet_header(
        wb,
        sheet,
        companies,
        max_date,
        min_date,
        deleted_missions=deleted_missions,
    )
    sheet.freeze_panes(row_idx, 2)

    for user, work_days in sorted(
        wdays_by_user.items(), key=lambda u: u[0].display_name
    ):
        user_starting_row_idx = row_idx
        col_idx = 0
        for wday in sorted(work_days, key=lambda wd: wd.day):
            workday_starting_row_idx = row_idx
            for mission in sorted(
                wday.missions, key=lambda mi: mi.creation_time
            ):
                if deleted_missions and not mission.is_deleted():
                    continue
                if not deleted_missions and (
                    mission.is_holiday() or mission.is_deleted()
                ):
                    continue
                first_activities_for_user = next(
                    iter(
                        mission.activities_for(
                            user=user, include_dismissed_activities=True
                        )
                    ),
                    None,
                )
                mission_starting_row_idx = row_idx
                if (
                    first_activities_for_user
                    and to_fr_tz(first_activities_for_user.start_time).date()
                    == wday.day
                ):
                    if row_idx == user_starting_row_idx:
                        column_base_formats = write_tab_headers(
                            wb, sheet, row_idx, all_columns
                        )
                        row_idx = (
                            user_starting_row_idx
                        ) = (
                            workday_starting_row_idx
                        ) = mission_starting_row_idx = (row_idx + 1)
                    for history_event in sorted(
                        mission.history, key=lambda ev: ev.time
                    ):
                        col_idx = 0
                        additional_format = {
                            "text_wrap": True,
                            "valign": "top",
                        }
                        if (
                            deleted_missions
                            and history_event.type == LogActionType.DELETE
                        ):
                            additional_format["color"] = red_hex

                        if mission_starting_row_idx == row_idx:
                            additional_format["top"] = 1
                        col_idx = write_cells(
                            wb,
                            sheet,
                            column_base_formats,
                            col_idx,
                            row_idx,
                            deleted_workday_columns
                            if deleted_missions
                            else workday_columns,
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
                if require_mission_name:
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
                to_fr_tz(wday.start_time) if wday.start_time else wday.day,
                formats.get("merged_date_format"),
            )
        merge_cells_if_needed(
            wb,
            sheet,
            user_starting_row_idx,
            row_idx + 1 if row_idx == (user_starting_row_idx + 1) else row_idx,
            0,
            f"{wday.user.display_name}\nIdentifiant : {wday.user.id}",
            formats.get("merged_top"),
        )
        for col_to_format in range(col_idx):
            sheet.write(
                row_idx,
                col_to_format,
                "",
                wb.add_format({"top": 1}),
            )

        if row_idx != user_starting_row_idx:
            row_idx += 2


workday_columns = [
    COLUMN_EMPLOYEE,
    COLUMN_DETAILS_DAY,
]
deleted_workday_columns = [COLUMN_EMPLOYEE, COLUMN_DAY]


def get_mission_columns(require_mission_name):
    mission_columns = []
    if require_mission_name:
        mission_columns.extend([COLUMN_MISSION])
    return mission_columns


event_columns = [
    COLUMN_EVENT_TIME,
    COLUMN_EVENT_AUTHOR,
    COLUMN_EVENT_AUTHOR_STATUS,
    COLUMN_EVENT_DESC,
    COLUMN_EVENT_ACTIVITIES,
    COLUMN_EVENT_OBSERVATIONS,
]
