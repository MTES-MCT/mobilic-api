import zipfile
from collections import defaultdict
from io import BytesIO

from xlsxwriter import Workbook

from app.helpers.time import FR_TIMEZONE
from app.helpers.xls.common import clean_string
from app.helpers.xls.companies.tab_activities import write_work_days_sheet
from app.helpers.xls.companies.tab_details import write_day_details_sheet
from app.helpers.xls.signature import HMAC_PROP_NAME, add_signature


def get_archive_excel_file(batches, companies, min_date, max_date):
    memory_file = BytesIO()
    with zipfile.ZipFile(
        memory_file, "w", compression=zipfile.ZIP_DEFLATED
    ) as zipObject:
        for idx_user, batch in enumerate(batches):
            (batch_user, batch_data) = batch
            excel_file = get_one_excel_file(
                batch_data, companies, min_date, max_date
            )
            last_name = clean_string(batch_user.last_name)
            first_name = clean_string(batch_user.first_name)
            user_name = f"{batch_user.id}_{last_name}_{first_name}"
            zipObject.writestr(f"{user_name}.xlsx", excel_file.getvalue())

    memory_file.seek(0)
    return memory_file


def get_one_excel_file(wdays_data, companies, min_date, max_date, tz=FR_TIMEZONE):
    complete_work_days = [wd for wd in wdays_data if wd.is_complete]
    wdays_by_user = defaultdict(list)
    wdays_by_user_deleted_missions = defaultdict(list)
    for work_day in complete_work_days:
        if len(work_day.activities) > 0:
            wdays_by_user[work_day.user].append(work_day)

        if len(work_day._all_activities) > 0:
            wdays_by_user_deleted_missions[work_day.user].append(work_day)

    require_expenditures = any([c.require_expenditures for c in companies])
    require_mission_name = any([c.require_mission_name for c in companies])
    require_kilometer_data = any([c.require_kilometer_data for c in companies])
    allow_transfers = any([c.allow_transfers for c in companies])

    output = BytesIO()
    wb = Workbook(output)
    wb.set_custom_property(HMAC_PROP_NAME, "a")

    write_work_days_sheet(
        wb,
        wdays_by_user,
        require_expenditures=require_expenditures,
        require_mission_name=require_mission_name,
        allow_transfers=allow_transfers,
        require_kilometer_data=require_kilometer_data,
        companies=companies,
        min_date=min_date,
        max_date=max_date,
    )
    write_day_details_sheet(
        wb,
        wdays_by_user,
        require_mission_name=require_mission_name,
        companies=companies,
        min_date=min_date,
        max_date=max_date,
        tz=tz
    )
    write_day_details_sheet(
        wb,
        wdays_by_user_deleted_missions,
        require_mission_name=require_mission_name,
        companies=companies,
        min_date=min_date,
        max_date=max_date,
        deleted_missions=True,
        tz=tz
    )
    wb.close()

    output.seek(0)
    output = add_signature(output)
    output.seek(0)
    return output
