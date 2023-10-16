from app.helpers.xls.legends import (
    write_bank_holiday_legend,
)


def write_sheet_legend(wb, sheet):
    write_bank_holiday_legend(wb, sheet, start_row=1, start_col=4)
