from collections import defaultdict
from flask import send_file, after_this_request
from xlsxwriter import Workbook
from datetime import timedelta
from io import BytesIO
import hmac
import hashlib
from zipfile import ZipFile
from defusedxml.ElementTree import parse

from app import app
from app.models.activity import ActivityType
from app.helpers.time import utc_to_fr

WORKSHEETS_TO_INCLUDE_IN_HMAC = ["xl/worksheets/sheet1.xml"]
HMAC_BLOCK_SIZE = 1024
HMAC_PROP_NAME = "Mobilic HMAC"
HMAC_KEY = (
    app.config["HMAC_SIGNING_KEY"].encode()
    if app.config["HMAC_SIGNING_KEY"]
    else None
)

ACTIVITY_TYPE_LABEL = {
    ActivityType.DRIVE: "conduite",
    ActivityType.WORK: "autre tâche",
    ActivityType.SUPPORT: "accompagnement",
}

EXCEL_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


class IntegrityVerificationError(Exception):
    code = None


class InvalidXlsxFormat(IntegrityVerificationError):
    code = "INVALID_FORMAT"


class MissingSignature(IntegrityVerificationError):
    code = "MISSING_SIGNATURE"


class SignatureDoesNotMatch(IntegrityVerificationError):
    code = "SIGNATURE_DOES_NOT_MATCH"


class UnavailableService(IntegrityVerificationError):
    code = "UNAVAILABLE"


columns_in_main_sheet = [
    ("Employé", lambda wday: wday.user.display_name, None, 30),
    ("Jour", lambda wday: utc_to_fr(wday.start_time), "date_format", 20,),
    ("Début", lambda wday: utc_to_fr(wday.start_time), "time_format", 15,),
    ("Fin", lambda wday: utc_to_fr(wday.end_time), "time_format", 15,),
    (
        "Conduite",
        lambda wday: timedelta(
            seconds=wday.activity_durations[ActivityType.DRIVE]
        ),
        "duration_format",
        10,
    ),
    (
        "Accompagnement",
        lambda wday: timedelta(
            seconds=wday.activity_durations[ActivityType.SUPPORT]
        ),
        "duration_format",
        10,
    ),
    (
        "Autre tâche",
        lambda wday: timedelta(
            seconds=wday.activity_durations[ActivityType.WORK]
        ),
        "duration_format",
        10,
    ),
    (
        "Pause",
        lambda wday: timedelta(
            seconds=wday.service_duration - wday.total_work_duration
        ),
        "duration_format",
        10,
    ),
    (
        "Repas jour",
        lambda wday: wday.expenditures.get("day_meal", 0),
        None,
        10,
    ),
    (
        "Repas nuit",
        lambda wday: wday.expenditures.get("night_meal", 0),
        None,
        10,
    ),
    (
        "Découchage",
        lambda wday: wday.expenditures.get("sleep_over", 0),
        None,
        10,
    ),
    (
        "Casse-croûte",
        lambda wday: wday.expenditures.get("snack", 0),
        None,
        10,
    ),
    (
        "Mission(s)",
        lambda wday: ", ".join([m.name for m in wday.missions if m.name]),
        None,
        30,
    ),
    (
        "Entreprise(s)",
        lambda wday: ", ".join([c.name for c in wday.companies if c.name]),
        None,
        30,
    ),
    (
        "Véhicule(s)",
        lambda wday: ", ".join(
            set(
                [
                    m.vehicle_name
                    for m in wday.missions
                    if m.vehicle_name is not None
                ]
            )
        ),
        None,
        30,
    ),
    (
        "Observations",
        lambda wday: "\n".join([" - " + c.text for c in wday.comments]),
        None,
        50,
    ),
]


def send_work_days_as_excel(user_wdays):
    complete_work_days = [wd for wd in user_wdays if wd.is_complete]
    output = BytesIO()
    wb = Workbook(output)
    wb.set_custom_property(HMAC_PROP_NAME, 1)

    date_formats = dict(
        date_format=wb.add_format({"num_format": "dd/mm/yyyy"}),
        time_format=wb.add_format({"num_format": "h:mm"}),
        duration_format=wb.add_format({"num_format": "[h]:mm"}),
    )
    formats = dict(bold=wb.add_format({"bold": True}), **date_formats)

    wdays_by_user = defaultdict(list)
    for work_day in complete_work_days:
        wdays_by_user[work_day.user].append(work_day)

    main_sheet = wb.add_worksheet("Activité")
    main_sheet.protect()
    main_row_idx = 1

    main_col_idx = 0
    for (main_col_name, resolver, _, column_width) in columns_in_main_sheet:
        main_sheet.write(0, main_col_idx, main_col_name, formats["bold"])
        main_sheet.set_column(main_col_idx, main_col_idx, column_width)
        main_col_idx += 1

    for user, work_days in wdays_by_user.items():
        for wday in sorted(work_days, key=lambda wd: wd.start_time):
            main_col_idx = 0
            for (main_col_name, resolver, style, _) in columns_in_main_sheet:
                if style in date_formats and resolver(wday) is not None:
                    main_sheet.write_datetime(
                        main_row_idx,
                        main_col_idx,
                        resolver(wday),
                        formats.get(style),
                    )
                else:
                    main_sheet.write(
                        main_row_idx,
                        main_col_idx,
                        resolver(wday),
                        formats.get(style),
                    )
                main_col_idx += 1
            main_row_idx += 1

    wb.close()

    output.seek(0)
    output = add_signature(output)
    output.seek(0)

    @after_this_request
    def change_cache_control_header(response):
        response.headers["Cache-Control"] = "no-cache"
        return response

    return send_file(
        output,
        mimetype=EXCEL_MIMETYPE,
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="rapport_activité.xlsx",
    )


def compute_hmac(archive, key):
    signature = hmac.new(key, digestmod=hashlib.sha256)
    for file_name in WORKSHEETS_TO_INCLUDE_IN_HMAC:
        with archive.open(file_name, "r") as f:
            while True:
                block = f.read(HMAC_BLOCK_SIZE)
                if not block:
                    break
                signature.update(block)
    return signature.hexdigest()


def extract_signature_node_from_xml(xml):
    root = xml.getroot()
    hmac_prop_value = None
    for child in root:
        if child.attrib.get("name") == HMAC_PROP_NAME:
            hmac_prop_value = child[0]
            break
    return hmac_prop_value


def add_signature(fp):
    if not HMAC_KEY:
        return fp
    new_archive_fp = BytesIO()
    with ZipFile(new_archive_fp, "w") as new_archive:
        with ZipFile(fp, "r") as archive:
            for file_name in archive.namelist():
                if file_name != "docProps/custom.xml":
                    with archive.open(file_name, "r") as f:
                        new_archive.writestr(file_name, f.read())

            signature = compute_hmac(archive, HMAC_KEY)

            with archive.open("docProps/custom.xml", "r") as f:
                xml = parse(f)
                hmac_prop_value = extract_signature_node_from_xml(xml)
                if hmac_prop_value is not None:
                    hmac_prop_value.text = signature

        custom_props_fp = BytesIO()
        xml.write(custom_props_fp, xml_declaration=True, encoding="UTF-8")
        custom_props_fp.seek(0)
        new_archive.writestr("docProps/custom.xml", custom_props_fp.read())

    return new_archive_fp


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
