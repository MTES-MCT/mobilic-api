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
    date_and_time_format={"num_format": "dd/mm/yyyy h:mm", "align": "center"},
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
    merged_date_format={
        "num_format": "dd/mm/yyyy",
        "align": "center",
        "valign": "vcenter",
        "border": 1,
    },
)
formats = dict(
    bold={"bold": True},
    wrap={"text_wrap": True},
    center={"align": "center"},
    merged_top={"bold": True, "valign": "top", "border": 1},
    merged_center={"valign": "vcenter", "align": "center", "border": 1},
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
        sheet.write(
            row_idx,
            col_idx,
            col_name,
            wb.add_format(
                {
                    "bold": True,
                    "bg_color": color,
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            ),
        )
        sheet.set_column(col_idx, col_idx, column_width)
        column_base_formats.append({"right": 1})
        col_idx += 1
    sheet.set_row(row_idx, 40)
    return column_base_formats


def write_cells(
    wb,
    sheet,
    column_base_formats,
    col_idx,
    row_idx,
    columns,
    resource_for_resolver,
    additional_format=None,
):
    for (
        col_name,
        resolver,
        style,
        *_,
    ) in columns:
        row_style = {
            **column_base_formats[col_idx],
            **(formats.get(style) or {}),
        }
        if additional_format:
            row_style.update(additional_format)
        if style in date_formats:
            sheet.write_datetime(
                row_idx,
                col_idx,
                resolver(resource_for_resolver),
                wb.add_format(row_style),
            )
        else:
            sheet.write(
                row_idx,
                col_idx,
                resolver(resource_for_resolver),
                wb.add_format(row_style),
            )
        col_idx += 1
    return col_idx


def merge_cells_if_needed(
    workbook, sheet, starting_row, current_row, col_idx, cell_text, cell_format
):
    if starting_row != current_row - 1:
        sheet.merge_range(
            starting_row,
            col_idx,
            current_row - 1,
            col_idx,
            cell_text,
            workbook.add_format(cell_format),
        )
