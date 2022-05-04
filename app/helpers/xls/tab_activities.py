from datetime import timedelta

from app.helpers.time import is_sunday_or_bank_holiday, to_fr_tz
from app.helpers.xls.common import (
    write_sheet_header,
    light_blue_hex,
    light_green_hex,
    light_red_hex,
    light_orange_hex,
    light_grey_hex,
    light_yellow_hex,
    green_hex,
    date_formats,
    formats,
    write_tab_headers,
    write_sheet_legend,
)
from app.models.activity import ActivityType


def write_work_days_sheet(
    wb,
    wdays_by_user,
    require_expenditures,
    require_mission_name,
    allow_transfers,
    require_kilometer_data,
    companies,
    min_date,
    max_date,
):
    sheet = wb.add_worksheet("Activité")
    sheet.protect()
    sheet.freeze_panes(3, 2)
    sheet.set_column(0, 4, 20)

    write_sheet_header(wb, sheet, companies, max_date, min_date)

    row_idx = 4
    columns_in_main_sheet = get_columns_in_main_sheet(
        require_expenditures,
        require_mission_name,
        allow_transfers,
        require_kilometer_data,
    )
    has_one_bank_holiday = False

    for user, work_days in sorted(
        wdays_by_user.items(), key=lambda u: u[0].first_name + u[0].last_name
    ):
        column_base_formats = write_tab_headers(
            wb, sheet, row_idx, columns_in_main_sheet
        )
        row_idx += 1
        user_starting_row_idx = row_idx
        for wday in sorted(work_days, key=lambda wd: wd.day):
            if is_sunday_or_bank_holiday(wday.day):
                has_one_bank_holiday = True
            col_idx = 0
            for (col_name, resolver, style, *_) in columns_in_main_sheet:
                column_style = style(wday)
                if column_style in date_formats and resolver(wday) is not None:
                    sheet.write_datetime(
                        row_idx,
                        col_idx,
                        resolver(wday),
                        wb.add_format(
                            {
                                **column_base_formats[col_idx],
                                **(formats.get(column_style) or {}),
                                "border": 1,
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
                                **(formats.get(column_style) or {}),
                                "border": 1,
                            }
                        ),
                    )
                col_idx += 1
            row_idx += 1

        if user_starting_row_idx != row_idx - 1:
            sheet.merge_range(
                user_starting_row_idx,
                0,
                row_idx - 1,
                0,
                wday.user.first_name + " " + wday.user.last_name,
                wb.add_format(
                    {
                        "bold": True,
                        "valign": "top",
                        "border": 1,
                    }
                ),
            )
        write_user_recap(
            wb,
            sheet,
            columns_in_main_sheet,
            user_starting_row_idx,
            row_idx - 1,
        )
        row_idx += 4
    if has_one_bank_holiday:
        write_sheet_legend(wb, sheet)


def write_user_recap(
    wb,
    sheet,
    columns_in_main_sheet,
    user_starting_row_idx,
    user_ending_row_idx,
):
    recap_col_idx = 0
    previous_has_to_be_summed = False
    for (_, _, style, _, _, has_to_be_summed) in columns_in_main_sheet:
        if has_to_be_summed:
            if not previous_has_to_be_summed:
                sheet.write(
                    user_ending_row_idx + 2,
                    recap_col_idx - 1,
                    "Total",
                    wb.add_format(
                        {
                            "bg_color": green_hex,
                            "align": "center",
                            "bold": True,
                            "border": 1,
                        }
                    ),
                )
            sheet.write_formula(
                user_ending_row_idx + 2,
                recap_col_idx,
                compute_excel_sum_col_range(
                    recap_col_idx, user_starting_row_idx, user_ending_row_idx
                ),
                wb.add_format(
                    {**(formats.get(style(None)) or {}), "border": 1}
                ),
            )
        previous_has_to_be_summed = has_to_be_summed
        recap_col_idx += 1


def get_columns_in_main_sheet(
    require_expenditures,
    require_mission_name,
    allow_transfers,
    require_kilometer_data,
):
    columns_in_main_sheet = [
        (
            "Employé",
            lambda wday: wday.user.first_name + " " + wday.user.last_name,
            lambda _: "bold",
            30,
            light_grey_hex,
            False,
        ),
        (
            "Jour",
            lambda wday: wday.day,
            lambda wday: "bank_holiday_date_format"
            if is_sunday_or_bank_holiday(wday.day)
            else "date_format",
            20,
            light_yellow_hex,
            False,
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
                    lambda _: "wrap",
                    30,
                    light_blue_hex,
                    False,
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
                lambda _: "wrap",
                30,
                light_blue_hex,
                False,
            ),
            (
                "Début",
                lambda wday: "-"
                if wday.is_first_mission_overlapping_with_previous_day
                else to_fr_tz(wday.start_time)
                if wday.start_time
                else None,
                lambda wday: "time_format"
                if not wday.is_first_mission_overlapping_with_previous_day
                else "center",
                15,
                light_green_hex,
                False,
            ),
            (
                "Fin",
                lambda wday: "-"
                if wday.is_last_mission_overlapping_with_next_day
                else to_fr_tz(wday.end_time)
                if wday.end_time
                else None,
                lambda wday: "time_format"
                if not wday.is_last_mission_overlapping_with_next_day
                else "center",
                15,
                light_green_hex,
                False,
            ),
            (
                "Conduite",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.DRIVE]
                ),
                lambda _: "duration_format",
                13,
                light_green_hex,
                True,
            ),
            (
                "Accompagnement",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.SUPPORT]
                ),
                lambda _: "duration_format",
                13,
                light_green_hex,
                True,
            ),
            (
                "Autre tâche",
                lambda wday: timedelta(
                    seconds=wday.activity_durations[ActivityType.WORK]
                ),
                lambda _: "duration_format",
                13,
                light_green_hex,
                True,
            ),
            (
                "Total travail",
                lambda wday: timedelta(seconds=wday.total_work_duration),
                lambda wday: "bank_holiday_duration_format"
                if wday and is_sunday_or_bank_holiday(wday.day)
                else "bold_duration_format",
                13,
                light_green_hex,
                True,
            ),
            (
                "Total travail de nuit",
                lambda wday: timedelta(seconds=wday.total_night_work_duration),
                lambda _: "duration_format",
                13,
                light_green_hex,
                True,
            ),
        ]
    )

    if allow_transfers:
        columns_in_main_sheet.extend(
            [
                (
                    "Liaison",
                    lambda wday: timedelta(
                        seconds=wday.activity_durations[ActivityType.TRANSFER]
                    ),
                    lambda _: "duration_format",
                    13,
                    light_green_hex,
                    True,
                ),
            ]
        )

    columns_in_main_sheet.extend(
        [
            (
                "Pause",
                lambda wday: timedelta(
                    seconds=wday.service_duration
                    - wday.total_work_duration
                    - wday.activity_durations[ActivityType.TRANSFER]
                ),
                lambda _: "duration_format",
                13,
                light_green_hex,
                True,
            ),
            (
                "Amplitude",
                lambda wday: timedelta(seconds=wday.service_duration),
                lambda _: "duration_format",
                13,
                light_green_hex,
                False,
            ),
            (
                "Lieu de début de service",
                lambda wday: wday.start_location.address.format()
                if wday.start_location
                else "",
                lambda _: "wrap",
                30,
                light_blue_hex,
                False,
            ),
        ]
    )

    if require_kilometer_data:
        columns_in_main_sheet.extend(
            [
                (
                    "Relevé km de début de service (si même véhicule utilisé au cours de la journée)",
                    lambda wday: format_kilometer_reading(
                        wday.start_location, wday
                    ),
                    lambda _: "center",
                    30,
                    light_blue_hex,
                    False,
                ),
            ]
        )
    columns_in_main_sheet.extend(
        [
            (
                "Lieu de fin de service",
                lambda wday: wday.end_location.address.format()
                if wday.end_location
                else "",
                lambda _: "wrap",
                30,
                light_blue_hex,
                False,
            ),
        ]
    )

    if require_kilometer_data:
        columns_in_main_sheet.extend(
            [
                (
                    "Relevé km de fin de service (si même véhicule utilisé au cours de la journée)",
                    lambda wday: format_kilometer_reading(
                        wday.end_location, wday
                    ),
                    lambda _: "center",
                    30,
                    light_blue_hex,
                    False,
                ),
                (
                    "Nombre de kilomètres parcourus",
                    lambda wday: format_kilometer_driven_in_wday(wday),
                    lambda _: "center",
                    30,
                    light_blue_hex,
                    True,
                ),
            ]
        )

    if require_expenditures:
        columns_in_main_sheet.extend(
            [
                (
                    "Repas midi",
                    lambda wday: wday.expenditures.get("day_meal", 0),
                    lambda _: "center",
                    13,
                    light_orange_hex,
                    True,
                ),
                (
                    "Repas soir",
                    lambda wday: wday.expenditures.get("night_meal", 0),
                    lambda _: "center",
                    13,
                    light_orange_hex,
                    True,
                ),
                (
                    "Découché",
                    lambda wday: wday.expenditures.get("sleep_over", 0),
                    lambda _: "center",
                    13,
                    light_orange_hex,
                    True,
                ),
                (
                    "Casse-croûte",
                    lambda wday: wday.expenditures.get("snack", 0),
                    lambda _: "center",
                    13,
                    light_orange_hex,
                    True,
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
                lambda _: "wrap",
                50,
                light_red_hex,
                False,
            ),
        ]
    )

    return columns_in_main_sheet


def format_kilometer_reading(location, wday):
    if (
        not wday.one_and_only_one_vehicle_used
        or not location
        or not location.kilometer_reading
    ):
        return ""
    return location.kilometer_reading


def format_kilometer_driven_in_wday(wday):
    if (
        not wday.one_and_only_one_vehicle_used
        or not wday.start_location
        or not wday.end_location
        or not wday.start_location.kilometer_reading
        or not wday.end_location.kilometer_reading
    ):
        return ""
    return (
        wday.end_location.kilometer_reading
        - wday.start_location.kilometer_reading
    )


def compute_excel_sum_col_range(col_idx, row_start, row_end):
    return "{{=SUM({0}{1}:{2}{3})}}".format(
        chr(col_idx + 65), row_start + 1, chr(col_idx + 65), row_end + 1
    )
