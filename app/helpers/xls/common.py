from io import BytesIO

from flask import send_file
from xlsxwriter import Workbook

from app.helpers.xls.signature import HMAC_PROP_NAME, add_signature

light_brown_hex = "#ffe599"
light_yellow_hex = "#fdffbc"
light_grey_hex = "#dadada"
light_blue_hex = "#b4e1fa"
light_green_hex = "#daf5e7"
light_orange_hex = "#fff0e4"
light_red_hex = "#d9d2e9"
green_hex = "#a8d08d"
very_light_red_hex = "#fcb4b4"

EXCEL_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

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
    merged_top={"bold": True, "valign": "top", "border": 1, "text_wrap": True},
    merged_center={"valign": "vcenter", "align": "center", "border": 1},
    **date_formats,
)


def write_tab_headers(wb, sheet, row_idx, columns):
    col_idx = 0
    column_base_formats = []
    for column in columns:
        sheet.write(
            row_idx,
            col_idx,
            column.label,
            wb.add_format(
                {
                    "bold": True,
                    "bg_color": column.color,
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            ),
        )
        sheet.set_column(col_idx, col_idx, column.width)
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
    with_border=False,
):
    for column in columns:
        style = column.lambda_style(resource_for_resolver)
        value = column.lambda_value(resource_for_resolver)
        row_style = {
            **column_base_formats[col_idx],
            **(formats.get(style) or {}),
        }
        if with_border:
            row_style["border"] = 1

        if additional_format:
            row_style.update(additional_format)
        write_method = "write_datetime" if style in date_formats else "write"
        getattr(sheet, write_method)(
            row_idx,
            col_idx,
            value,
            wb.add_format(row_style),
        )
        col_idx += 1
    return col_idx


def merge_cells_if_needed(
    workbook, sheet, starting_row, current_row, col_idx, cell_text, cell_format
):
    if starting_row <= current_row - 1:
        sheet.merge_range(
            starting_row,
            col_idx,
            current_row - 1,
            col_idx,
            cell_text,
            workbook.add_format(cell_format),
        )


def write_user_recap(
    wb,
    sheet,
    columns,
    user_starting_row_idx,
    user_ending_row_idx,
    user_display_name,
):
    recap_col_idx = 0
    previous_has_to_be_summed = False
    for column in columns:
        if column.is_to_be_summed:
            if not previous_has_to_be_summed:
                text_to_write = f"Total {user_display_name}"
                row_ = user_ending_row_idx + 2
                col_ = recap_col_idx - 1
                # Merge with left cell to match figma
                sheet.merge_range(
                    row_,
                    col_ - 1,
                    row_,
                    col_,
                    text_to_write,
                    wb.add_format(
                        {
                            "bg_color": green_hex,
                            "align": "center",
                            "bold": True,
                            "border": 1,
                        }
                    ),
                )
            sheet.write_formula(
                user_ending_row_idx + 2,
                recap_col_idx,
                compute_excel_sum_col_range(
                    recap_col_idx, user_starting_row_idx, user_ending_row_idx
                ),
                wb.add_format(
                    {
                        **(formats.get(column.lambda_style(None)) or {}),
                        "border": 1,
                    }
                ),
            )
        previous_has_to_be_summed = column.is_to_be_summed
        recap_col_idx += 1


def compute_excel_sum_col_range(col_idx, row_start, row_end):
    return "{{=SUM({0}{1}:{2}{3})}}".format(
        chr(col_idx + 65), row_start + 1, chr(col_idx + 65), row_end + 1
    )


def clean_string(s):
    return "".join(filter(str.isalnum, s))


class ExcelWriter:
    def __init__(self, add_signature=True):
        self.output = None
        self.wb = None
        self.add_signature = add_signature

    def __enter__(self):
        self.output = BytesIO()
        self.wb = Workbook(self.output)
        self.wb.set_custom_property(HMAC_PROP_NAME, "a")
        return self.wb, self.output

    def __exit__(self, *a):
        self.wb.close()
        self.output.seek(0)
        if self.add_signature:
            self.output = add_signature(self.output)
            self.output.seek(0)


def send_excel_file(file, name):
    return send_file(
        file,
        mimetype=EXCEL_MIMETYPE,
        as_attachment=True,
        cache_timeout=0,
        attachment_filename=name,
    )
