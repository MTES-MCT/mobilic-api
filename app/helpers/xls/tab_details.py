from app.helpers.time import to_fr_tz
from app.helpers.xls.common import (
    write_sheet_header,
    light_grey_hex,
    light_yellow_hex,
    light_blue_hex,
    light_green_hex,
    light_red_hex,
    date_formats,
    formats,
    very_light_red_hex,
    write_tab_headers,
)
from app.models.activity import ActivityType

ACTIVITY_TYPE_LABEL = {
    ActivityType.DRIVE: "conduite",
    ActivityType.WORK: "autre tâche",
    ActivityType.SUPPORT: "accompagnement",
    ActivityType.TRANSFER: "temps de liaison",
}


def write_day_details_sheet(
    wb, wdays_by_user, require_mission_name, companies, min_date, max_date
):
    sheet = wb.add_worksheet("Détails")
    sheet.protect()

    sheet.freeze_panes(3, 0)
    write_sheet_header(wb, sheet, companies, max_date, min_date)

    all_columns = [
        *get_columns_in_details_sheet(require_mission_name),
        *activity_version_columns_in_details_sheet,
    ]

    row_idx = 3

    for user, work_days in wdays_by_user.items():
        column_base_formats = write_tab_headers(
            wb, sheet, row_idx, all_columns
        )
        row_idx += 1
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
        row_idx += 2


def get_columns_in_details_sheet(require_mission_name):
    activity_columns_in_details_sheet = [
        (
            "Employé",
            lambda wday: wday.user.first_name + " " + wday.user.last_name,
            "bold",
            30,
            light_grey_hex,
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
    return activity_columns_in_details_sheet


activity_version_columns_in_details_sheet = [
    (
        "Date et heure de l'enregistrement",
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
        "Statut de l'auteur",
        lambda av_or_a, pav, is_delete: "A FAIRE",
        None,
        30,
        light_green_hex,
    ),
    (
        "Description de l'enregistrement",
        lambda av_or_a, pav, is_delete: format_activity_version_description(
            av_or_a, pav, is_delete
        ),
        None,
        50,
        light_green_hex,
    ),
    # (
    #     "Activités effectuées",
    #     lambda a: ACTIVITY_TYPE_LABEL[a.type],
    #     None,
    #     15,
    #     light_blue_hex,
    # ),
    (
        "Observations",
        lambda av_or_a, pav, is_delete: (
            (av_or_a.context if not is_delete else av_or_a.dismiss_context)
            or {}
        ).get("comment"),
        "wrap",
        60,
        light_red_hex,
    ),
]


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
