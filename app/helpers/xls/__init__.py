import hmac
import zipfile
from abc import ABC
from collections import defaultdict
from io import BytesIO
from zipfile import ZipFile

from defusedxml.ElementTree import parse
from flask import after_this_request, send_file
from xlsxwriter import Workbook

from app import app, MobilicError
from app.helpers.xls.signature import (
    add_signature,
    HMAC_PROP_NAME,
    HMAC_KEY,
    extract_signature_node_from_xml,
    compute_hmac,
)
from app.helpers.xls.tab_activities import write_work_days_sheet
from app.helpers.xls.tab_details import write_day_details_sheet

EXCEL_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


class IntegrityVerificationError(MobilicError, ABC):
    pass


class InvalidXlsxFormat(IntegrityVerificationError):
    code = "INVALID_FORMAT"


class MissingSignature(IntegrityVerificationError):
    code = "MISSING_SIGNATURE"


class SignatureDoesNotMatch(IntegrityVerificationError):
    code = "SIGNATURE_DOES_NOT_MATCH"


class UnavailableService(IntegrityVerificationError):
    code = "UNAVAILABLE"


def send_work_days_as_excel(user_wdays_batches, companies, min_date, max_date):
    @after_this_request
    def change_cache_control_header(response):
        response.headers["Cache-Control"] = "no-cache"
        return response

    if len(user_wdays_batches) == 1:
        return send_work_days_as_one_excel_file(
            user_wdays_batches[0][1], companies, min_date, max_date
        )
    else:
        return send_work_days_as_one_archive(
            user_wdays_batches, companies, min_date, max_date
        )


def send_work_days_as_one_excel_file(
    user_wdays, companies, min_date, max_date
):
    excel_file = get_one_excel_file(user_wdays, companies, min_date, max_date)

    return send_file(
        excel_file,
        mimetype=EXCEL_MIMETYPE,
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="rapport_activité.xlsx",
    )


def send_work_days_as_one_archive(batches, companies, min_date, max_date):
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
    return send_file(
        memory_file,
        mimetype="zip",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="rapport_activités.zip",
    )


def get_one_excel_file(wdays_data, companies, min_date, max_date):
    complete_work_days = [wd for wd in wdays_data if wd.is_complete]
    output = BytesIO()
    wb = Workbook(output)
    wb.set_custom_property(HMAC_PROP_NAME, "a")

    wdays_by_user = defaultdict(list)
    for work_day in complete_work_days:
        if len(work_day.activities) > 0:
            wdays_by_user[work_day.user].append(work_day)

    require_expenditures = any([c.require_expenditures for c in companies])
    require_mission_name = any([c.require_mission_name for c in companies])
    require_kilometer_data = any([c.require_kilometer_data for c in companies])
    allow_transfers = any([c.allow_transfers for c in companies])

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
    )

    wb.close()

    output.seek(0)
    output = add_signature(output)
    output.seek(0)
    return output


def retrieve_and_verify_signature(fp):
    if not HMAC_KEY:
        raise UnavailableService()
    try:
        with ZipFile(fp, "r") as archive:
            if "docProps/custom.xml" not in archive.namelist():
                raise MissingSignature()
            with archive.open("docProps/custom.xml", "r") as f:
                xml = parse(f)
                existing_signature_node = extract_signature_node_from_xml(xml)
                if existing_signature_node is None:
                    raise MissingSignature()
                existing_signature = existing_signature_node.text
            if not existing_signature or len(existing_signature) <= 1:
                raise MissingSignature()
            actual_signature = compute_hmac(archive, HMAC_KEY)
        if not hmac.compare_digest(existing_signature, actual_signature):
            raise SignatureDoesNotMatch()

    except IntegrityVerificationError as e:
        raise e
    except Exception as e:
        app.logger.exception(e)
        raise InvalidXlsxFormat()


def clean_string(s):
    return "".join(filter(str.isalnum, s))
