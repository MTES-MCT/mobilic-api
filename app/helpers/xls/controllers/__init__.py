from app.helpers.xls.common import ExcelWriter, send_excel_file
from app.helpers.xls.controllers.tab_details_single_control import (
    write_details_sheet,
)
from app.helpers.xls.controllers.tab_main_single_control import (
    write_main_sheet,
)


def send_control_as_one_excel_file(
    control, work_days_data, min_date, max_date
):
    with ExcelWriter() as (wb, output):
        wdays_with_activities = list(
            filter(lambda wd: len(wd.activities) > 0, work_days_data)
        )
        write_main_sheet(
            wb, control, wdays_with_activities, min_date, max_date
        )
        write_details_sheet(
            wb, control, wdays_with_activities, min_date, max_date
        )

    return send_excel_file(
        file=output, name=f"Contrôle_Mobilic_#{control.id}.xlsx"
    )
