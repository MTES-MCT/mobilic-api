from app.domain.business import get_businesses_display_name
from app.domain.regulations import get_default_business
from app.models.controller_control import ControlType
from app.templates.filters import MONTHS


def write_header(wb, sheet, control):

    is_control_mobilic = control.control_type == ControlType.mobilic

    control_date_time = (
        control.qr_code_generation_time
        if control.qr_code_generation_time
        else control.creation_time
    )
    month_id = control_date_time.month
    items = [
        (
            "Contrôle",
            f"{control_date_time.strftime('%d')} {MONTHS[month_id - 1]} {control_date_time.strftime('%Y à %Hh%M')}",
        )
    ]

    control_user_name = (
        control.user.display_name
        if control.user
        else f"{control.user_first_name} {control.user_last_name}"
    )
    items.append(("Nom du salarié", control_user_name))

    if control.user:
        items.append(("Identifiant du salarié", f"{control.user.id}"))

    items.append(
        (
            "Entreprise au moment du contrôle"
            if is_control_mobilic
            else "Entreprise",
            control.company_name,
        )
    )
    items.append(
        (
            "Véhicule au moment du contrôle"
            if is_control_mobilic
            else "Véhicule",
            control.vehicle_registration_number,
        )
    )

    if is_control_mobilic:
        business_ids = list(
            control.control_bulletin.get("employments_business_types").values()
        )
        businesses_str = get_businesses_display_name(business_ids=business_ids)
        items.append(
            (
                "Type(s) d’activité",
                businesses_str,
            )
        )
    else:
        business_id = control.control_bulletin.get("business_id", None)
        business = get_default_business(business_id=business_id)
        items.append(
            (
                "Type d’activité",
                business.display_name,
            )
        )

    if is_control_mobilic:
        max_date = control.history_end_date
        min_date = control.history_start_date
        items.append(
            (
                "Période des données contrôlées",
                f"du {min_date.strftime('%d/%m/%Y')} au {max_date.strftime('%d/%m/%Y')}",
            )
        )
    items.append(
        ("Nombre d'infractions retenues", f"{control.nb_reported_infractions}")
    )
    items.append(("Notes", control.note))
    for idx, item in enumerate(items):
        sheet.write(
            idx,
            0,
            f"{item[0]} :",
            wb.add_format({"bold": True, "valign": "top"}),
        )
        if idx == len(items) - 1:
            sheet.merge_range(
                idx,
                1,
                idx,
                6,
                item[1],
                wb.add_format({"text_wrap": True, "valign": "top"}),
            )
            sheet.set_row(idx, 60)
        else:
            sheet.write(idx, 1, item[1])

    nb_rows_used = len(items) + 2
    sheet.freeze_panes(nb_rows_used + 1, 0)
    sheet.set_column(0, 2, 20)
    return nb_rows_used
