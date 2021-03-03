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

WORKSHEETS_TO_INCLUDE_IN_HMAC = [
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet2.xml",
]
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

light_yellow_hex = "#fdffbc"
light_blue_hex = "#b4e1fa"
light_green_hex = "#daf5e7"
light_orange_hex = "#fff0e4"
light_red_hex = "#efaca6"
very_light_red_hex = "#fcb4b4"


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


date_formats = dict(
    date_format={"num_format": "dd/mm/yyyy"},
    date_and_time_format={"num_format": "dd/mm/yyyy h:mm"},
    time_format={"num_format": "h:mm"},
    duration_format={"num_format": "[h]:mm"},
)
formats = dict(bold={"bold": True}, **date_formats)


def format_activity_version_description(version, previous_version, is_delete):
    if is_delete:
        return f"Suppression de l'activité"
    if not previous_version:
        if not version.end_time:
            return f"Début de l'activité à {utc_to_fr(version.start_time).strftime('%H:%M')}"
        else:
            return f"Création a posteriori de l'activité sur la période {utc_to_fr(version.start_time).strftime('%H:%M')} - {utc_to_fr(version.end_time).strftime('%H:%M')}"
    else:
        if (
            not previous_version.end_time
            and version.end_time
            and version.start_time == previous_version.start_time
        ):
            return f"Fin de l'activité à {utc_to_fr(version.end_time).strftime('%H:%M')}"
        if not previous_version.end_time and not version.end_time:
            return f"Correction du début de l'activité de {utc_to_fr(previous_version.start_time).strftime('%H:%M')} à {utc_to_fr(version.start_time).strftime('%H:%M')}"
        if previous_version.start_time == version.start_time:
            return f"Correction de la fin de l'activité de {utc_to_fr(previous_version.end_time).strftime('%H:%M') if previous_version.end_time else ''} à {utc_to_fr(version.end_time).strftime('%H:%M') if version.end_time else ''}"
        return f"Correction de la période d'activité de {utc_to_fr(previous_version.start_time).strftime('%H:%M')} - {utc_to_fr(previous_version.end_time).strftime('%H:%M') if previous_version.end_time else ''} à {utc_to_fr(version.start_time).strftime('%H:%M')} - {utc_to_fr(version.end_time).strftime('%H:%M') if version.end_time else ''}"


columns_in_main_sheet = [
    (
        "Employé",
        lambda wday: wday.user.display_name,
        None,
        30,
        light_yellow_hex,
    ),
    (
        "Jour",
        lambda wday: utc_to_fr(wday.start_time),
        "date_format",
        20,
        light_yellow_hex,
    ),
    (
        "Mission(s)",
        lambda wday: ", ".join([m.name for m in wday.missions if m.name]),
        None,
        30,
        light_blue_hex,
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
        light_blue_hex,
    ),
    (
        "Début",
        lambda wday: utc_to_fr(wday.start_time),
        "time_format",
        15,
        light_green_hex,
    ),
    (
        "Fin",
        lambda wday: utc_to_fr(wday.end_time),
        "time_format",
        15,
        light_green_hex,
    ),
    (
        "Conduite",
        lambda wday: timedelta(
            seconds=wday.activity_durations[ActivityType.DRIVE]
        ),
        "duration_format",
        10,
        light_green_hex,
    ),
    (
        "Accompagnement",
        lambda wday: timedelta(
            seconds=wday.activity_durations[ActivityType.SUPPORT]
        ),
        "duration_format",
        10,
        light_green_hex,
    ),
    (
        "Autre tâche",
        lambda wday: timedelta(
            seconds=wday.activity_durations[ActivityType.WORK]
        ),
        "duration_format",
        10,
        light_green_hex,
    ),
    (
        "Pause",
        lambda wday: timedelta(
            seconds=wday.service_duration - wday.total_work_duration
        ),
        "duration_format",
        10,
        light_green_hex,
    ),
    (
        "Repas jour",
        lambda wday: wday.expenditures.get("day_meal", 0),
        None,
        10,
        light_orange_hex,
    ),
    (
        "Repas nuit",
        lambda wday: wday.expenditures.get("night_meal", 0),
        None,
        10,
        light_orange_hex,
    ),
    (
        "Découchage",
        lambda wday: wday.expenditures.get("sleep_over", 0),
        None,
        10,
        light_orange_hex,
    ),
    (
        "Casse-croûte",
        lambda wday: wday.expenditures.get("snack", 0),
        None,
        10,
        light_orange_hex,
    ),
    (
        "Observations",
        lambda wday: "\n".join([" - " + c.text for c in wday.comments]),
        None,
        50,
        light_red_hex,
    ),
    (
        "Entreprise(s)",
        lambda wday: ", ".join([c.name for c in wday.companies if c.name]),
        None,
        30,
        light_blue_hex,
    ),
]


activity_columns_in_details_sheet = [
    ("Employé", lambda a: a.user.display_name, None, 30, light_yellow_hex,),
    (
        "Jour",
        lambda a: utc_to_fr(a.start_time),
        "date_format",
        20,
        light_yellow_hex,
    ),
    ("Mission", lambda a: a.mission.name, None, 20, light_blue_hex,),
    (
        "Activité",
        lambda a: ACTIVITY_TYPE_LABEL[a.type],
        None,
        15,
        light_blue_hex,
    ),
    (
        "Début",
        lambda a: utc_to_fr(a.start_time),
        "time_format",
        10,
        light_blue_hex,
    ),
    (
        "Fin",
        lambda a: utc_to_fr(a.end_time) if a.end_time else None,
        "time_format",
        10,
        light_blue_hex,
    ),
]

activity_version_columns_in_details_sheet = [
    (
        "Description de l'enregistrement",
        lambda av_or_a, pav, is_delete: format_activity_version_description(
            av_or_a, pav, is_delete
        ),
        None,
        50,
        light_green_hex,
    ),
    (
        "Heure de l'enregistrement",
        lambda av_or_a, pav, is_delete: utc_to_fr(
            av_or_a.reception_time if not is_delete else av_or_a.dismissed_at
        ),
        "date_and_time_format",
        20,
        light_green_hex,
    ),
    (
        "Auteur de l'enregistrement",
        lambda av_or_a, pav, is_delete: (
            av_or_a.submitter if not is_delete else av_or_a.dismiss_author
        ).display_name,
        None,
        30,
        light_green_hex,
    ),
    (
        "Commentaire",
        lambda av_or_a, pav, is_delete: (
            (av_or_a.context if not is_delete else av_or_a.dismiss_context)
            or {}
        ).get("comment"),
        None,
        60,
        light_red_hex,
    ),
]


def write_work_days_sheet(wb, wdays_by_user):
    sheet = wb.add_worksheet("Activité")
    sheet.protect()
    sheet.freeze_panes(1, 2)
    row_idx = 1

    col_idx = 0
    column_base_formats = []
    for (col_name, resolver, _, column_width, color,) in columns_in_main_sheet:
        right_border = 0
        if col_idx == 1:
            right_border = 2
        elif (
            col_idx < len(columns_in_main_sheet) - 1
            and columns_in_main_sheet[col_idx + 1][4] != color
        ):
            right_border = 1
        sheet.write(
            0,
            col_idx,
            col_name,
            wb.add_format(
                {
                    "bold": True,
                    "bg_color": color,
                    "right": right_border,
                    "align": "center",
                    "valign": "center",
                }
            ),
        )
        sheet.set_column(col_idx, col_idx, column_width)
        column_base_formats.append({"right": right_border})
        col_idx += 1

    sheet.set_row(0, 40)

    for user, work_days in wdays_by_user.items():
        for wday in sorted(work_days, key=lambda wd: wd.start_time):
            col_idx = 0
            for (col_name, resolver, style, *_) in columns_in_main_sheet:
                if style in date_formats and resolver(wday) is not None:
                    sheet.write_datetime(
                        row_idx,
                        col_idx,
                        resolver(wday),
                        wb.add_format(
                            {
                                **column_base_formats[col_idx],
                                **(formats.get(style) or {}),
                            }
                        ),
                    )
                else:
                    sheet.write(
                        row_idx,
                        col_idx,
                        resolver(wday),
                        wb.add_format(
                            {
                                **column_base_formats[col_idx],
                                **(formats.get(style) or {}),
                            }
                        ),
                    )
                col_idx += 1
            row_idx += 1


def write_day_details_sheet(wb, wdays_by_user):
    sheet = wb.add_worksheet("Détails")
    sheet.protect()
    all_columns = [
        *activity_columns_in_details_sheet,
        *activity_version_columns_in_details_sheet,
    ]
    # sheet.freeze_panes(1, 2)
    row_idx = 1

    col_idx = 0
    column_base_formats = []
    for (col_name, resolver, _, column_width, color,) in all_columns:
        right_border = 0
        if (
            col_idx < len(all_columns) - 1
            and all_columns[col_idx + 1][4] != color
        ):
            right_border = 1
        sheet.write(
            0,
            col_idx,
            col_name,
            wb.add_format(
                {
                    "bold": True,
                    "bg_color": color,
                    "right": right_border,
                    "align": "center",
                    "valign": "center",
                }
            ),
        )
        sheet.set_column(col_idx, col_idx, column_width)
        column_base_formats.append({"right": right_border})
        col_idx += 1

    sheet.set_row(0, 40)

    for user, work_days in wdays_by_user.items():
        for wday in sorted(work_days, key=lambda wd: wd.start_time):
            for activity in wday._all_activities:
                starting_row_idx = row_idx
                activity_versions = sorted(
                    activity.revisions, key=lambda r: r.version
                )
                events = [
                    (version, previous_version, False)
                    for (version, previous_version) in zip(
                        activity_versions, [None, *activity_versions[:-1]]
                    )
                    if not previous_version
                    or version.start_time != previous_version.start_time
                    or version.end_time != previous_version.end_time
                ]
                if activity.is_dismissed:
                    events.append((activity, None, True))
                for (av_or_a, previous_version, is_delete) in events:
                    col_idx = len(activity_columns_in_details_sheet)
                    for (
                        col_name,
                        resolver,
                        style,
                        *_,
                    ) in activity_version_columns_in_details_sheet:
                        if (
                            style in date_formats
                            and resolver(av_or_a, previous_version, is_delete)
                            is not None
                        ):
                            sheet.write_datetime(
                                row_idx,
                                col_idx,
                                resolver(av_or_a, previous_version, is_delete),
                                wb.add_format(
                                    {
                                        **column_base_formats[col_idx],
                                        **(formats.get(style) or {}),
                                    }
                                ),
                            )
                        else:
                            sheet.write(
                                row_idx,
                                col_idx,
                                resolver(av_or_a, previous_version, is_delete),
                                wb.add_format(
                                    {
                                        **column_base_formats[col_idx],
                                        **(formats.get(style) or {}),
                                    }
                                ),
                            )
                        col_idx += 1

                    row_idx += 1
                col_idx = 0
                for (
                    col_name,
                    resolver,
                    style,
                    *_,
                ) in activity_columns_in_details_sheet:
                    cell_format = wb.add_format(
                        {
                            **column_base_formats[col_idx],
                            **(formats.get(style) or {}),
                            **(
                                {"bg_color": very_light_red_hex}
                                if activity.is_dismissed
                                else {}
                            ),
                        }
                    )
                    sheet.merge_range(
                        starting_row_idx,
                        col_idx,
                        row_idx - 1,
                        col_idx,
                        "",
                        cell_format,
                    )
                    if (
                        style in date_formats
                        and resolver(activity) is not None
                    ):
                        sheet.write_datetime(
                            starting_row_idx,
                            col_idx,
                            resolver(activity),
                            cell_format,
                        )
                    else:
                        sheet.write(
                            starting_row_idx,
                            col_idx,
                            resolver(activity),
                            cell_format,
                        )
                    col_idx += 1


def send_work_days_as_excel(user_wdays):
    complete_work_days = [wd for wd in user_wdays if wd.is_complete]
    output = BytesIO()
    wb = Workbook(output)
    wb.set_custom_property(HMAC_PROP_NAME, "a")

    wdays_by_user = defaultdict(list)
    for work_day in complete_work_days:
        wdays_by_user[work_day.user].append(work_day)

    write_work_days_sheet(wb, wdays_by_user)
    write_day_details_sheet(wb, wdays_by_user)

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
