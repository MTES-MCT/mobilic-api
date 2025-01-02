from datetime import datetime

from app.helpers.xls.common import (
    write_tab_headers,
    write_cells,
    merge_cells_if_needed,
    formats,
)
from app.helpers.xls.controllers.header import write_header
from app.helpers.xls.columns import *

COLUMNS_WORKDAY = [
    COLUMN_ENTREPRISE,
    COLUMN_SIREN,
    COLUMN_DETAILS_DAY,
]
COLUMNS_MISSION = [COLUMN_MISSION]
COLUMNS_EVENT = [
    COLUMN_EVENT_TIME,
    COLUMN_EVENT_AUTHOR,
    COLUMN_EVENT_AUTHOR_STATUS,
    COLUMN_EVENT_DESC,
    COLUMN_EVENT_ACTIVITIES,
    COLUMN_EVENT_OBSERVATIONS,
]
COLUMNS_ALL = [
    *COLUMNS_WORKDAY,
    *COLUMNS_MISSION,
    *COLUMNS_EVENT,
    COLUMN_INFRACTIONS_FOR_DAY,
]


def write_details_sheet(wb, control, work_days_data):
    sheet = wb.add_worksheet(f"Détail Contrôle #{control.id}")
    sheet.protect()

    row_idx = write_header(wb, sheet, control)

    column_base_formats = write_tab_headers(wb, sheet, row_idx, COLUMNS_ALL)
    row_idx += 1

    recap_start_row = row_idx

    for wday in sorted(work_days_data, key=lambda wd: wd.day):
        infractions_for_day = [
            infraction
            for infraction in control.reported_infractions
            if datetime.strptime(infraction.get("date"), "%Y-%m-%d").date()
            == wday.day
        ]
        if len(infractions_for_day) == 0:
            text_infractions = "Pas d'infraction retenue"
        else:
            text_infractions = ",\n".join(
                [i.get("sanction", "") for i in infractions_for_day]
            )
        workday_starting_row_idx = row_idx
        for mission in sorted(
            wday.missions, key=lambda mission: mission.creation_time
        ):
            first_activities_for_user = next(
                iter(mission.activities_for(control.user, True)), None
            )
            mission_starting_row_idx = row_idx

            ## skip mission if necessary
            if (
                not first_activities_for_user
                or to_fr_tz(first_activities_for_user.start_time).date()
                != wday.day
            ):
                continue

            for history_event in sorted(
                mission.history, key=lambda ev: ev.time
            ):
                col_idx = 0
                col_idx = write_cells(
                    wb,
                    sheet,
                    column_base_formats,
                    col_idx,
                    row_idx,
                    COLUMNS_WORKDAY,
                    wday,
                )
                col_idx = write_cells(
                    wb,
                    sheet,
                    column_base_formats,
                    col_idx,
                    row_idx,
                    COLUMNS_MISSION,
                    mission,
                )

                additional_format = {
                    "text_wrap": True,
                    "valign": "top",
                }
                if mission_starting_row_idx == row_idx:
                    additional_format["top"] = 1

                col_idx = write_cells(
                    wb,
                    sheet,
                    column_base_formats,
                    col_idx,
                    row_idx,
                    COLUMNS_EVENT,
                    history_event,
                    additional_format,
                )
                row_idx += 1
            merge_cells_if_needed(
                wb,
                sheet,
                mission_starting_row_idx,
                row_idx,
                col_idx,
                text_infractions,
                formats.get("merged_center"),
            )
            merge_cells_if_needed(
                wb,
                sheet,
                mission_starting_row_idx,
                row_idx,
                3,
                mission.name,
                formats.get("merged_center"),
            )
            merge_cells_if_needed(
                wb,
                sheet,
                workday_starting_row_idx,
                row_idx,
                2,
                to_fr_tz(wday.start_time),
                formats.get("merged_date_format"),
            )
            for col_to_format in range(col_idx):
                sheet.write(
                    row_idx,
                    col_to_format,
                    "",
                    wb.add_format({"top": 1}),
                )

        merge_cells_if_needed(
            wb,
            sheet,
            recap_start_row,
            row_idx,
            1,
            COLUMN_SIREN.lambda_value(wday),
            formats.get("merged_center"),
        )
        merge_cells_if_needed(
            wb,
            sheet,
            recap_start_row,
            row_idx,
            0,
            COLUMN_ENTREPRISE.lambda_value(wday),
            formats.get("merged_center"),
        )
