import zipfile
from collections import defaultdict
from flask import send_file, after_this_request
from abc import ABC
from xlsxwriter import Workbook
from datetime import timedelta
from io import BytesIO
import hmac
import hashlib
from zipfile import ZipFile, ZIP_DEFLATED
from defusedxml.ElementTree import parse

from app import app, MobilicError
from app.models.activity import ActivityType
from app.helpers.time import to_fr_tz

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
    ActivityType.TRANSFER: "temps de liaison",
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


date_formats = dict(
    date_format={"num_format": "dd/mm/yyyy"},
    date_and_time_format={"num_format": "dd/mm/yyyy h:mm"},
    time_format={"num_format": "h:mm"},
    duration_format={"num_format": "[h]:mm"},
)
formats = dict(bold={"bold": True}, wrap={"text_wrap": True}, **date_formats)


def format_activity_version_description(version, previous_version, is_delete):
    if is_delete:
        return f"Suppression de l'activité"
    if not previous_version:
        if not version.end_time:
            return f"Début de l'activité à {to_fr_tz(version.start_time).strftime('%H:%M')}"
        else:
            return f"Création a posteriori de l'activité sur la période {to_fr_tz(version.start_time).strftime('%H:%M')} - {to_fr_tz(version.end_time).strftime('%H:%M')}"
    else:
        if (
            not previous_version.end_time
            and version.end_time
            and version.start_time == previous_version.start_time
        ):
            return f"Fin de l'activité à {to_fr_tz(version.end_time).strftime('%H:%M')}"
        if not previous_version.end_time and not version.end_time:
            return f"Correction du début de l'activité de {to_fr_tz(previous_version.start_time).strftime('%H:%M')} à {to_fr_tz(version.start_time).strftime('%H:%M')}"
        if previous_version.start_time == version.start_time:
            return f"Correction de la fin de l'activité de {to_fr_tz(previous_version.end_time).strftime('%H:%M') if previous_version.end_time else ''} à {to_fr_tz(version.end_time).strftime('%H:%M') if version.end_time else ''}"
        return f"Correction de la période d'activité de {to_fr_tz(previous_version.start_time).strftime('%H:%M')} - {to_fr_tz(previous_version.end_time).strftime('%H:%M') if previous_version.end_time else ''} à {to_fr_tz(version.start_time).strftime('%H:%M')} - {to_fr_tz(version.end_time).strftime('%H:%M') if version.end_time else ''}"


def format_kilometer_reading(location, wday):
    if (
        not wday.one_and_only_one_vehicle_used
        or not location
        or not location.kilometer_reading
    ):
        return ""
    return location.kilometer_reading


def get_columns_in_main_sheet(require_expenditures, require_mission_name):
    columns_in_main_sheet = [
        (
            "Prénom",
            lambda wday: wday.user.first_name,
            "wrap",
            30,
            light_yellow_hex,
        ),
        (
            "Nom",
            lambda wday: wday.user.last_name,
            "wrap",
            30,
            light_yellow_hex,
        ),
        (
            "Jour",
            lambda wday: wday.day,
            "date_format",
            20,
            light_yellow_hex,
        ),
    ]

    if require_mission_name:
        columns_in_main_sheet.extend(
            [
                (
                    "Mission(s)",
                    lambda wday: ", ".join(
                        [m.name for m in wday.missions if m.name]
                    ),
                    "wrap",
                    30,
                    light_blue_hex,
                )
            ]
        )

    columns_in_main_sheet.extend(
        [
            (
                "Véhicule(s)",
                lambda wday: ", ".join(
                    set(
                        [
                            m.vehicle.name
                            for m in wday.missions
                            if m.vehicle is not None
                        ]
                    )
                ),
                "wrap",
                30,
                light_blue_hex,
            ),
            (
                "Début",
                lambda wday: to_fr_tz(wday.start_time)
                if wday.start_time
                else None,
                "time_format",
                15,
                light_green_hex,
            ),
            (
                "Fin",
                lambda wday: to_fr_tz(wday.end_time)
                if wday.end_time
                else None,
                "time_format",
                15,
                light_green_hex,
            ),
            (
                "Amplitude",
                lambda wday: timedelta(seconds=wday.service_duration),
                "duration_format",
                13,
                light_green_hex,
            ),
            (
                "Total travail",
                lambda wday: timedelta(seconds=wday.total_work_duration),
                "duration_format",
                13,
                light_green_hex,
            ),
            (
                "Conduite",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.DRIVE]
                ),
                "duration_format",
                13,
                light_green_hex,
            ),
            (
                "Accompagnement",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.SUPPORT]
                ),
                "duration_format",
                13,
                light_green_hex,
            ),
            (
                "Autre tâche",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.WORK]
                ),
                "duration_format",
                13,
                light_green_hex,
            ),
            (
                "Liaison",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.TRANSFER]
                ),
                "duration_format",
                13,
                light_green_hex,
            ),
            (
                "Pause",
                lambda wday: timedelta(
                    seconds=wday.service_duration
                    - wday.total_work_duration
                    - wday.activity_durations[ActivityType.TRANSFER]
                ),
                "duration_format",
                13,
                light_green_hex,
            ),
        ]
    )
    if require_expenditures:
        columns_in_main_sheet.extend(
            [
                (
                    "Repas midi",
                    lambda wday: wday.expenditures.get("day_meal", 0),
                    None,
                    13,
                    light_orange_hex,
                ),
                (
                    "Repas soir",
                    lambda wday: wday.expenditures.get("night_meal", 0),
                    None,
                    13,
                    light_orange_hex,
                ),
                (
                    "Découché",
                    lambda wday: wday.expenditures.get("sleep_over", 0),
                    None,
                    13,
                    light_orange_hex,
                ),
                (
                    "Casse-croûte",
                    lambda wday: wday.expenditures.get("snack", 0),
                    None,
                    13,
                    light_orange_hex,
                ),
            ]
        )

    columns_in_main_sheet.extend(
        [
            (
                "Observations",
                lambda wday: "\n".join(
                    [" - " + c.text for c in wday.comments]
                ),
                "wrap",
                50,
                light_red_hex,
            ),
            (
                "Lieu de début de service",
                lambda wday: wday.start_location.address.format()
                if wday.start_location
                else "",
                "wrap",
                30,
                light_blue_hex,
            ),
            (
                "Relevé km de début de service (si même véhicule utilisé au cours de la journée)",
                lambda wday: format_kilometer_reading(
                    wday.start_location, wday
                ),
                None,
                30,
                light_blue_hex,
            ),
            (
                "Lieu de fin de service",
                lambda wday: wday.end_location.address.format()
                if wday.end_location
                else "",
                "wrap",
                30,
                light_blue_hex,
            ),
            (
                "Relevé km de fin de service (si même véhicule utilisé au cours de la journée)",
                lambda wday: format_kilometer_reading(wday.end_location, wday),
                None,
                30,
                light_blue_hex,
            ),
            (
                "Entreprise(s)",
                lambda wday: ", ".join(
                    [c.name for c in wday.companies if c.name]
                ),
                "wrap",
                50,
                light_blue_hex,
            ),
        ]
    )

    return columns_in_main_sheet


def get_columns_in_details_sheet(require_mission_name):
    activity_columns_in_details_sheet = [
        (
            "Prénom",
            lambda a: a.user.first_name,
            None,
            30,
            light_yellow_hex,
        ),
        (
            "Nom",
            lambda a: a.user.last_name,
            None,
            30,
            light_yellow_hex,
        ),
        (
            "Jour",
            lambda a: to_fr_tz(a.start_time),
            "date_format",
            20,
            light_yellow_hex,
        ),
    ]
    if require_mission_name:
        activity_columns_in_details_sheet.extend(
            [
                (
                    "Mission",
                    lambda a: a.mission.name,
                    None,
                    20,
                    light_blue_hex,
                )
            ]
        )
    activity_columns_in_details_sheet.extend(
        [
            (
                "Activité",
                lambda a: ACTIVITY_TYPE_LABEL[a.type],
                None,
                15,
                light_blue_hex,
            ),
            (
                "Début",
                lambda a: to_fr_tz(a.start_time),
                "time_format",
                10,
                light_blue_hex,
            ),
            (
                "Fin",
                lambda a: to_fr_tz(a.end_time) if a.end_time else None,
                "time_format",
                10,
                light_blue_hex,
            ),
        ]
    )
    return activity_columns_in_details_sheet


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
        lambda av_or_a, pav, is_delete: to_fr_tz(
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
        "Observation",
        lambda av_or_a, pav, is_delete: (
            (av_or_a.context if not is_delete else av_or_a.dismiss_context)
            or {}
        ).get("comment"),
        "wrap",
        60,
        light_red_hex,
    ),
]


def write_work_days_sheet(
    wb, wdays_by_user, require_expenditures, require_mission_name
):
    sheet = wb.add_worksheet("Activité")
    sheet.protect()
    sheet.freeze_panes(1, 2)
    row_idx = 1
    columns_in_main_sheet = get_columns_in_main_sheet(
        require_expenditures, require_mission_name
    )

    col_idx = 0
    column_base_formats = []
    for (
        col_name,
        resolver,
        _,
        column_width,
        color,
    ) in columns_in_main_sheet:
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
                    "text_wrap": True,
                }
            ),
        )
        sheet.set_column(col_idx, col_idx, column_width)
        column_base_formats.append({"right": right_border})
        col_idx += 1

    sheet.set_row(0, 40)

    for user, work_days in wdays_by_user.items():
        for wday in sorted(work_days, key=lambda wd: wd.day):
            if wday.activities:
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


def write_day_details_sheet(wb, wdays_by_user, require_mission_name):
    sheet = wb.add_worksheet("Détails")
    sheet.protect()
    all_columns = [
        *get_columns_in_details_sheet(require_mission_name),
        *activity_version_columns_in_details_sheet,
    ]
    # sheet.freeze_panes(1, 2)
    row_idx = 1

    col_idx = 0
    column_base_formats = []
    for (
        col_name,
        resolver,
        _,
        column_width,
        color,
    ) in all_columns:
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
        acts = set()
        for wday in work_days:
            acts = acts | set(wday._all_activities)
        for activity in sorted(acts, key=lambda a: a.start_time):
            starting_row_idx = row_idx
            activity_versions = sorted(
                activity.versions, key=lambda r: r.version_number
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
                col_idx = len(
                    get_columns_in_details_sheet(require_mission_name)
                )
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
            ) in get_columns_in_details_sheet(require_mission_name):
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
                if style in date_formats and resolver(activity) is not None:
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


def get_one_excel_file(wdays_data, companies):
    complete_work_days = [wd for wd in wdays_data if wd.is_complete]
    output = BytesIO()
    wb = Workbook(output)
    wb.set_custom_property(HMAC_PROP_NAME, "a")

    wdays_by_user = defaultdict(list)
    for work_day in complete_work_days:
        wdays_by_user[work_day.user].append(work_day)

    require_expenditures = any([c.require_expenditures for c in companies])
    require_mission_name = any([c.require_mission_name for c in companies])

    write_work_days_sheet(
        wb,
        wdays_by_user,
        require_expenditures=require_expenditures,
        require_mission_name=require_mission_name,
    )
    write_day_details_sheet(
        wb, wdays_by_user, require_mission_name=require_mission_name
    )

    wb.close()

    output.seek(0)
    output = add_signature(output)
    output.seek(0)
    return output


def send_work_days_as_one_archive(batches, companies):
    memory_file = BytesIO()
    with zipfile.ZipFile(
        memory_file, "w", compression=zipfile.ZIP_DEFLATED
    ) as zipObject:
        for idx_user, batch in enumerate(batches):
            excel_file = get_one_excel_file(batch, companies)
            user_name = f"employé_{idx_user + 1}"
            zipObject.writestr(f"{user_name}.xlsx", excel_file.getvalue())

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="zip",
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="rapport_activités.zip",
    )


def send_work_days_as_one_excel_file(user_wdays, companies):
    excel_file = get_one_excel_file(user_wdays, companies)

    return send_file(
        excel_file,
        mimetype=EXCEL_MIMETYPE,
        as_attachment=True,
        cache_timeout=0,
        attachment_filename="rapport_activité.xlsx",
    )


def send_work_days_as_excel(user_wdays_batches, companies):
    @after_this_request
    def change_cache_control_header(response):
        response.headers["Cache-Control"] = "no-cache"
        return response

    if len(user_wdays_batches) == 1:
        return send_work_days_as_one_excel_file(
            user_wdays_batches[0], companies
        )
    else:
        return send_work_days_as_one_archive(user_wdays_batches, companies)


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
    with ZipFile(new_archive_fp, "w", compression=ZIP_DEFLATED) as new_archive:
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
