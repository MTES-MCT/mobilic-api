from io import BytesIO

from xlsxwriter import Workbook

from app.helpers.xls.common import send_excel_file
from app.helpers.xls.controllers.tab_details_single_control import (
    write_details_sheet,
)
from app.helpers.xls.controllers.tab_main_single_control import (
    write_main_sheet,
)
from app.models.controller_control import ControlType


def _get_file_name(control):
    if control.control_type == ControlType.lic_papier:
        return f"Contrôle_Mobilic_LIC_papier_#{control.id}.xlsx"

    if control.control_type == ControlType.sans_lic:
        return f"Contrôle_Mobilic_pas_de_LIC_#{control.id}.xlsx"

    return f"Contrôle_Mobilic_#{control.id}.xlsx"


def send_control_as_one_excel_file(control):
    output = BytesIO()
    wb = Workbook(output)

    wdays_with_activities = None
    if control.control_type == ControlType.mobilic:
        max_date = control.history_end_date
        min_date = control.history_start_date
        from app import group_user_events_by_day_with_limit

        work_days_data = group_user_events_by_day_with_limit(
            control.user,
            from_date=min_date,
            until_date=max_date,
            include_dismissed_or_empty_days=True,
            max_reception_time=control.qr_code_generation_time,
        )[0]

        wdays_with_activities = list(
            filter(lambda wd: len(wd.activities) > 0, work_days_data)
        )

    write_main_sheet(wb, control, wdays_with_activities)

    if control.control_type == ControlType.mobilic:
        write_details_sheet(wb, control, wdays_with_activities)

    wb.close()
    output.seek(0)

    return send_excel_file(file=output, name=_get_file_name(control))
