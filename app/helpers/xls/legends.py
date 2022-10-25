from datetime import datetime
from app.helpers.xls.common import formats


def write_bank_holiday_legend(wb, sheet, start_row, start_col):
    sheet.write(
        start_row,
        start_col,
        "Légende :",
        wb.add_format({"bold": True}),
    )
    sheet.write_datetime(
        start_row + 1,
        start_col,
        datetime(2022, 1, 1, 0, 0),
        wb.add_format(
            {**formats.get("bank_holiday_date_format"), "border": 1}
        ),
    )
    sheet.write(
        start_row + 1,
        start_col + 1,
        "Dimanches ou jours fériés : jours de travail majorés",
        wb.add_format({"bold": True}),
    )


def write_breached_rule_legend(wb, sheet, start_row, start_col):
    sheet.write_datetime(
        start_row,
        start_col,
        datetime(2022, 1, 1, 9, 30),
        wb.add_format(
            {
                **formats.get("time_format"),
                "border": 1,
                "color": "red",
                "bold": True,
            }
        ),
    )
    sheet.write(
        start_row,
        start_col + 1,
        "Dépassement des seuils réglementaires",
        wb.add_format({"bold": True}),
    )
