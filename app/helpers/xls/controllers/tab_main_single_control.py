from datetime import datetime

from app.domain.business import get_businesses_display_name
from app.helpers.time import is_sunday_or_bank_holiday
from app.helpers.xls.common import (
    write_tab_headers,
    write_cells,
    write_user_recap,
    light_brown_hex,
    merge_cells_if_needed,
    formats,
)
from app.helpers.xls.companies.legend import write_sheet_legend
from app.helpers.xls.controllers.header import write_header
from app.helpers.xls.columns import *
from app.models.controller_control import ControlType

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
    COLUMN_OFF_HOURS,
    COLUMN_OFF_REASONS,
    COLUMN_OBSERVATIONS,
    COLUMN_NB_INFRACTIONS,
    COLUMN_INFRACTIONS_BUSINESS_TYPES,
]

COLUMNS_LIC_PAPIER = [
    COLUMN_DAY,
    COLUMN_NB_INFRACTIONS,
    COLUMN_INFRACTIONS_FOR_DAY,
]


def write_main_sheet(wb, control, work_days_data=None):
    sheet = wb.add_worksheet(f"Contrôle #{control.id}")
    sheet.protect()
    row_idx = write_header(wb, sheet, control)

    if control.control_type == ControlType.mobilic:
        _write_main_sheet_mobilic(
            wb=wb,
            sheet=sheet,
            row_idx=row_idx,
            work_days_data=work_days_data,
            control=control,
        )
    else:
        _write_main_sheet_mobilic_lic_papier(
            wb=wb, sheet=sheet, row_idx=row_idx, control=control
        )


def _write_main_sheet_mobilic(wb, sheet, row_idx, work_days_data, control):
    column_base_formats = write_tab_headers(wb, sheet, row_idx, COLUMNS_MAIN)
    row_idx += 1

    recap_start_row = row_idx
    has_one_bank_holiday = False
    has_one_day_off = False
    if work_days_data:
        for wday in sorted(work_days_data, key=lambda wd: wd.day):
            infractions_for_day = control.get_reported_infractions_for_day(
                day=wday.day
            )
            nb_infractions_for_day = len(infractions_for_day)
            wday.nb_infractions_for_day = nb_infractions_for_day

            infractions_business_ids = [
                inf.get("business_id") for inf in infractions_for_day
            ]
            infractions_business_types = get_businesses_display_name(
                business_ids=infractions_business_ids
            )
            wday.infractions_business_types = infractions_business_types

            is_day_off = all([m.is_holiday() for m in wday.missions])
            is_sunday_or_bank_holiday_ = is_sunday_or_bank_holiday(wday.day)
            bg_color = None
            if is_sunday_or_bank_holiday_:
                has_one_bank_holiday = True
                bg_color = light_brown_hex
            if is_day_off:
                has_one_day_off = True
                bg_color = blue_hex

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
                bg_color=bg_color,
            )
            row_idx += 1
            merge_cells_if_needed(
                wb,
                sheet,
                recap_start_row,
                row_idx,
                1,
                COLUMN_SIREN.lambda_value(wday),
                formats.get("merged_center"),
            )
            merge_cells_if_needed(
                wb,
                sheet,
                recap_start_row,
                row_idx,
                0,
                COLUMN_ENTREPRISE.lambda_value(wday),
                formats.get("merged_center"),
            )

    write_user_recap(
        wb,
        sheet,
        COLUMNS_MAIN,
        recap_start_row,
        row_idx - 1,
        control.user.display_name,
    )

    write_sheet_legend(
        wb,
        sheet,
        has_bank_holiday=has_one_bank_holiday,
        has_off_day=has_one_day_off,
    )


def _write_main_sheet_mobilic_lic_papier(wb, sheet, row_idx, control):
    write_tab_headers(wb, sheet, row_idx, COLUMNS_LIC_PAPIER)
    row_idx += 1
    infractions_by_date = {}
    for infraction in control.reported_infractions:
        infraction_date = datetime.strptime(
            infraction.get("date"), "%Y-%m-%d"
        ).date()
        if infraction_date in infractions_by_date:
            infractions_by_date[infraction_date].append(infraction)
        else:
            infractions_by_date[infraction_date] = [infraction]

    def _write_centered(_col_idx, _value, _additional_format={}):
        sheet.write(
            row_idx,
            _col_idx,
            _value,
            wb.add_format({**{"align": "center"}, **_additional_format}),
        )

    for infraction_date in sorted(infractions_by_date):
        _write_centered(
            _col_idx=0,
            _value=infraction_date,
            _additional_format={"num_format": "dd/mm/yyyy"},
        )
        _write_centered(
            _col_idx=1, _value=len(infractions_by_date[infraction_date])
        )
        _write_centered(
            _col_idx=2,
            _value=", ".join(
                [
                    i.get("sanction")
                    for i in infractions_by_date[infraction_date]
                ]
            ),
        )
        row_idx += 1
