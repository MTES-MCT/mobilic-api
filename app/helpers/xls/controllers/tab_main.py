from app.helpers.xls.common import (
    write_tab_headers,
    write_cells,
    write_user_recap,
)
from app.helpers.xls.controllers.header import write_header
from app.helpers.xls.columns import *
from app.helpers.xls.controllers.legend import write_sheet_legend

COLUMNS_MAIN = [
    COLUMN_ENTREPRISE,
    COLUMN_SIREN,
    COLUMN_DAY,
    COLUMN_VEHICLES,
    COLUMN_START,
    COLUMN_END,
    COLUMN_DRIVE,
    COLUMN_SUPPORT,
    COLUMN_OTHER_TASK,
    COLUMN_TOTAL_WORK,
    COLUMN_NIGHTLY_HOURS,
    COLUMN_BREAK,
    COLUMN_AMPLITUDE,
    COLUMN_START_LOCATION,
    COLUMN_START_KM,
    COLUMN_END_LOCATION,
    COLUMN_END_KM,
    COLUMN_TOTAL_KM,
    COLUMN_EXPENDITURE_DAY_MEAL,
    COLUMN_EXPENDITURE_NIGHT_MEAL,
    COLUMN_EXPENDITURE_SLEEP_OVER,
    COLUMN_EXPENDITURE_SNACK,
    COLUMN_OBSERVATIONS,
    COLUMN_BREACHED_RULES,
]


def write_main_sheet(
    wb, control, work_days_data, min_date, max_date, column_base_formats=None
):
    print(control)
    sheet = wb.add_worksheet(f"Contrôle #{control.id}")
    sheet.protect()
    write_header(wb, sheet, control, min_date, max_date)

    row_idx = 5
    column_base_formats = write_tab_headers(wb, sheet, row_idx, COLUMNS_MAIN)
    row_idx += 1

    recap_start_row = row_idx
    has_one_bank_holiday = False
    for wday in sorted(work_days_data, key=lambda wd: wd.day):
        col_idx = 0
        write_cells(
            wb,
            sheet,
            column_base_formats,
            col_idx,
            row_idx,
            COLUMNS_MAIN,
            wday,
            with_border=True,
        )
        row_idx += 1
        has_one_bank_holiday = (
            has_one_bank_holiday or is_sunday_or_bank_holiday(wday.day)
        )

    write_user_recap(
        wb,
        sheet,
        COLUMNS_MAIN,
        recap_start_row,
        row_idx - 1,
        wday.user.display_name,
    )

    if has_one_bank_holiday:
        write_sheet_legend(wb, sheet)
