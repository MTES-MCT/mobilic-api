from app.helpers.xls.columns import *
from app.helpers.xls.common import (
    formats,
    write_tab_headers,
    merge_cells_if_needed,
    write_cells,
    write_user_recap,
)
from app.helpers.xls.companies.headers import write_sheet_header
from app.helpers.xls.companies.legend import write_sheet_legend


def write_work_days_sheet(
    wb,
    wdays_by_user,
    require_expenditures,
    require_mission_name,
    allow_transfers,
    require_kilometer_data,
    companies,
    min_date,
    max_date,
):
    sheet = wb.add_worksheet("Activités")
    sheet.protect()
    sheet.freeze_panes(3, 2)
    sheet.set_column(0, 4, 20)

    write_sheet_header(wb, sheet, companies, max_date, min_date)

    row_idx = 4
    columns_in_main_sheet = get_columns_in_main_sheet(
        require_expenditures,
        require_mission_name,
        allow_transfers,
        require_kilometer_data,
    )
    has_one_bank_holiday = False

    for user, work_days in sorted(
        wdays_by_user.items(), key=lambda u: u[0].display_name
    ):
        column_base_formats = write_tab_headers(
            wb, sheet, row_idx, columns_in_main_sheet
        )
        row_idx += 1
        user_starting_row_idx = row_idx
        for wday in sorted(work_days, key=lambda wd: wd.day):
            if is_sunday_or_bank_holiday(wday.day):
                has_one_bank_holiday = True
            col_idx = 0
            write_cells(
                wb,
                sheet,
                column_base_formats,
                col_idx,
                row_idx,
                columns_in_main_sheet,
                wday,
                with_border=True,
            )
            row_idx += 1

        merge_cells_if_needed(
            wb,
            sheet,
            user_starting_row_idx,
            row_idx,
            0,
            f"{wday.user.display_name}\nIdentifiant : {wday.user.id}",
            formats.get("merged_top"),
        )

        write_user_recap(
            wb,
            sheet,
            columns_in_main_sheet,
            user_starting_row_idx,
            row_idx - 1,
            wday.user.display_name,
        )
        row_idx += 4
    if has_one_bank_holiday:
        write_sheet_legend(wb, sheet)


def get_columns_in_main_sheet(
    require_expenditures,
    require_mission_name,
    allow_transfers,
    require_kilometer_data,
):
    columns_in_main_sheet = [
        COLUMN_EMPLOYEE,
        COLUMN_DAY,
    ]

    if require_mission_name:
        columns_in_main_sheet.extend([COLUMN_MISSIONS])

    columns_in_main_sheet.extend(
        [
            COLUMN_VEHICLES,
            COLUMN_START,
            COLUMN_END,
            COLUMN_DRIVE,
            COLUMN_SUPPORT,
            COLUMN_OTHER_TASK,
            COLUMN_TOTAL_WORK,
            COLUMN_NIGHTLY_HOURS,
        ]
    )

    if allow_transfers:
        columns_in_main_sheet.extend(
            [
                COLUMN_TRANSFER,
            ]
        )

    columns_in_main_sheet.extend(
        [
            COLUMN_BREAK,
            COLUMN_AMPLITUDE,
            COLUMN_START_LOCATION,
        ]
    )

    if require_kilometer_data:
        columns_in_main_sheet.extend(
            [
                COLUMN_START_KM,
            ]
        )
    columns_in_main_sheet.extend(
        [
            COLUMN_END_LOCATION,
        ]
    )

    if require_kilometer_data:
        columns_in_main_sheet.extend(
            [
                COLUMN_END_KM,
                COLUMN_TOTAL_KM,
            ]
        )

    if require_expenditures:
        columns_in_main_sheet.extend(
            [
                COLUMN_EXPENDITURE_DAY_MEAL,
                COLUMN_EXPENDITURE_NIGHT_MEAL,
                COLUMN_EXPENDITURE_SLEEP_OVER,
                COLUMN_EXPENDITURE_SNACK,
            ]
        )

    columns_in_main_sheet.extend(
        [
            COLUMN_OBSERVATIONS,
        ]
    )

    return columns_in_main_sheet
