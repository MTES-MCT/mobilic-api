from app.templates.filters import MONTHS


def write_header(wb, sheet, control, min_date, max_date):
    control_date_time = control.qr_code_generation_time
    month_id = control_date_time.month
    items = [
        f"Contrôle : {control_date_time.strftime('%d')} {MONTHS[month_id - 1]} {control_date_time.strftime('%Y à %Hh%M')}",
        f"Nom du salarié : {control.user.display_name}",
        f"Identifiant du salarié : {control.user.id}",
        f"Période des données contrôlées : du {min_date.strftime('%d/%m/%Y')} au {max_date.strftime('%d/%m/%Y')}",
        f"Nombre d'infractions retenues : {control.nb_reported_infractions}",
    ]
    for idx, item in enumerate(items):
        sheet.write(idx, 0, item, wb.add_format({"bold": True}))
    sheet.freeze_panes(len(items) + 2, 2)
    sheet.set_column(0, 2, 20)
