from datetime import datetime
from app.helpers.xls.common import formats, light_brown_hex, blue_hex


def write_legend(
    wb, sheet, start_row, start_col, has_bank_holiday=False, has_off_day=False
):
    sheet.write(
        start_row,
        start_col,
        "Légende :",
        wb.add_format({"bold": True}),
    )
    next_row = start_row + 1
    if has_bank_holiday:
        sheet.write_datetime(
            next_row,
            start_col,
            datetime(2022, 1, 1, 0, 0),
            wb.add_format(
                {
                    **formats.get("date_format"),
                    "border": 1,
                    "bold": True,
                    "bg_color": light_brown_hex,
                }
            ),
        )
        sheet.write(
            next_row,
            start_col + 1,
            "Dimanches ou jours fériés : jours de travail majorés",
            wb.add_format({"bold": True}),
        )
        next_row += 1
    if has_off_day:
        sheet.write(
            next_row,
            start_col,
            datetime(2022, 1, 1, 0, 0),
            wb.add_format(
                {
                    **formats.get("date_format"),
                    "border": 1,
                    "bold": True,
                    "bg_color": blue_hex,
                }
            ),
        )
        sheet.write(
            next_row,
            start_col + 1,
            "Jours de congé ou d’absence",
            wb.add_format({"bold": True}),
        )
