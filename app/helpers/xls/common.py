from datetime import datetime

light_brown_hex = "#ffe599"
light_yellow_hex = "#fdffbc"
light_grey_hex = "#dadada"
light_blue_hex = "#b4e1fa"
light_green_hex = "#daf5e7"
light_orange_hex = "#fff0e4"
light_red_hex = "#d9d2e9"
green_hex = "#a8d08d"
very_light_red_hex = "#fcb4b4"

date_formats = dict(
    date_format={"num_format": "dd/mm/yyyy"},
    date_and_time_format={"num_format": "dd/mm/yyyy h:mm"},
    time_format={"num_format": "h:mm", "align": "center"},
    duration_format={"num_format": "[h]:mm", "align": "center"},
    bold_duration_format={
        "num_format": "[h]:mm",
        "align": "center",
        "bold": True,
    },
    bank_holiday_duration_format={
        "num_format": "[h]:mm",
        "align": "center",
        "bg_color": light_brown_hex,
        "bold": True,
    },
    bank_holiday_date_format={
        "num_format": "dd/mm/yyyy",
        "bg_color": light_brown_hex,
    },
)
formats = dict(
    bold={"bold": True},
    wrap={"text_wrap": True},
    center={"align": "center"},
    **date_formats,
)


def write_sheet_header(wb, sheet, companies, max_date, min_date):
    sheet.write(
        0,
        0,
        "Entreprise : {0}".format(", ".join(c.name for c in companies)),
        wb.add_format({"bold": True}),
    )
    sheet.write(
        1,
        0,
        "Date des données exportées : du {0} au {1}".format(
            min_date.strftime("%d/%m/%Y"), max_date.strftime("%d/%m/%Y")
        ),
        wb.add_format({"bold": True}),
    )


def write_sheet_legend(wb, sheet):
    sheet.write(
        0,
        4,
        "Légende :",
        wb.add_format({"bold": True}),
    )
    sheet.write_datetime(
        1,
        4,
        datetime(2022, 1, 1, 0, 0),
        wb.add_format(
            {**formats.get("bank_holiday_date_format"), "border": 1}
        ),
    )
    sheet.write(
        1,
        5,
        "Dimanches ou jours fériés : jours de travail majorés",
        wb.add_format({"bold": True}),
    )


def write_tab_headers(wb, sheet, row_idx, columns_in_main_sheet):
    col_idx = 0
    column_base_formats = []
    for (
        col_name,
        _,
        _,
        column_width,
        color,
        *_,
    ) in columns_in_main_sheet:
        if col_idx == 1:
            right_border = 2
        else:
            right_border = 1
        sheet.write(
            row_idx,
            col_idx,
            col_name,
            wb.add_format(
                {
                    "bold": True,
                    "bg_color": color,
                    "border": 1,
                    "right": right_border,
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            ),
        )
        sheet.set_column(col_idx, col_idx, column_width)
        column_base_formats.append({"right": right_border})
        col_idx += 1
    sheet.set_row(row_idx, 40)
    return column_base_formats
