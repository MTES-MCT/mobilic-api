from app.helpers.xls.legends import write_legend


def write_sheet_legend(wb, sheet, has_bank_holiday=False, has_off_day=False):
    if has_bank_holiday or has_off_day:
        write_legend(
            wb,
            sheet,
            start_row=0,
            start_col=4,
            has_bank_holiday=has_bank_holiday,
            has_off_day=has_off_day,
        )
