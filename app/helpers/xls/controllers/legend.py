from app.helpers.xls.legends import (
    write_bank_holiday_legend,
    write_breached_rule_legend,
)


def write_sheet_legend(wb, sheet):
    write_bank_holiday_legend(wb, sheet, start_row=1, start_col=4)
    write_breached_rule_legend(wb, sheet, start_row=3, start_col=4)
