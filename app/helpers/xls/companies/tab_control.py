from collections import defaultdict

from app.helpers.pdf.control_bulletin import NATINF_METADATA
from app.helpers.xls.columns import ExcelColumn, very_light_red_hex, light_grey_hex
from app.helpers.xls.common import (
    formats,
    write_tab_headers,
    merge_cells_if_needed,
    write_cells,
    get_filtered_alerts_by_day,
)
from app.helpers.xls.companies.headers import write_sheet_header


class InfractionRow:
    def __init__(self, natinf, nature, count, dates, qualification, definition):
        self.natinf = natinf
        self.nature = nature
        self.count = count
        self.dates = dates
        self.qualification = qualification
        self.definition = definition


COLUMN_CTRL_NATINF = ExcelColumn(
    "NATINF",
    lambda r: r.natinf,
    lambda _: "center",
    12,
    light_grey_hex,
)
COLUMN_CTRL_NATURE = ExcelColumn(
    "Nature",
    lambda r: r.nature,
    lambda _: "wrap",
    30,
    light_grey_hex,
)
COLUMN_CTRL_NB = ExcelColumn(
    "Nb",
    lambda r: r.count,
    lambda _: "center",
    8,
    light_grey_hex,
)
COLUMN_CTRL_DATE = ExcelColumn(
    "Date",
    lambda r: r.dates,
    lambda _: "wrap",
    30,
    light_grey_hex,
)
COLUMN_CTRL_QUALIFICATION = ExcelColumn(
    "Qualification",
    lambda r: r.qualification,
    lambda _: "wrap",
    60,
    light_grey_hex,
)
COLUMN_CTRL_DEFINIE_PAR = ExcelColumn(
    "Définie par",
    lambda r: r.definition,
    lambda _: "wrap",
    60,
    light_grey_hex,
)

COLUMN_CTRL_EMPLOYEE = ExcelColumn(
    "Employé",
    lambda _: "",
    lambda _: None,
    25,
    light_grey_hex,
)

COLUMNS_CONTROL = [
    COLUMN_CTRL_EMPLOYEE,
    COLUMN_CTRL_NATINF,
    COLUMN_CTRL_NATURE,
    COLUMN_CTRL_NB,
    COLUMN_CTRL_DATE,
    COLUMN_CTRL_QUALIFICATION,
    COLUMN_CTRL_DEFINIE_PAR,
]

COLUMNS_CONTROL_DATA = COLUMNS_CONTROL[1:]


def write_control_sheet(
    wb, wdays_by_user, companies, min_date, max_date
):
    sheet = wb.add_worksheet("Contrôle")
    sheet.protect()

    write_sheet_header(wb, sheet, companies, max_date, min_date)

    row_idx = 3
    for user in sorted(
        wdays_by_user.keys(), key=lambda u: u.display_name
    ):
        grouped = _collect_user_infractions(
            user.id, min_date, max_date
        )
        if not grouped:
            continue

        column_base_formats = write_tab_headers(
            wb, sheet, row_idx, COLUMNS_CONTROL
        )
        row_idx += 1
        user_start_row = row_idx

        for sanction_code in sorted(grouped.keys()):
            info = grouped[sanction_code]
            natinf_number = sanction_code.replace("NATINF ", "")
            metadata = NATINF_METADATA.get(natinf_number, {})
            dates_str = ", ".join(
                d.strftime("%d/%m/%Y") for d in sorted(info["dates"])
            )

            row = InfractionRow(
                natinf=natinf_number,
                nature=metadata.get("nature", ""),
                count=info["count"],
                dates=dates_str,
                qualification=metadata.get("qualification", ""),
                definition=metadata.get("definition", ""),
            )
            write_cells(
                wb,
                sheet,
                column_base_formats,
                1,
                row_idx,
                COLUMNS_CONTROL_DATA,
                row,
                additional_format={"valign": "vcenter"},
                with_border=True,
            )
            row_idx += 1

        merge_cells_if_needed(
            wb,
            sheet,
            user_start_row,
            row_idx,
            0,
            f"{user.display_name}\nIdentifiant : {user.id}",
            formats.get("merged_top"),
        )
        row_idx += 1


def _collect_user_infractions(user_id, min_date, max_date):
    alerts_by_day = get_filtered_alerts_by_day(
        user_id, min_date, max_date
    )
    grouped = defaultdict(lambda: {"count": 0, "dates": set()})
    for day, day_alerts in alerts_by_day.items():
        for alert in day_alerts:
            code = alert.extra["sanction_code"]
            grouped[code]["count"] += 1
            grouped[code]["dates"].add(day)
    return grouped
