def write_sheet_header(wb, sheet, companies, max_date, min_date):
    sheet.write(
        0,
        0,
        "Entreprise : {0}".format(", ".join(c.name for c in companies)),
        wb.add_format({"bold": True}),
    )
    sheet.write(
        1,
        0,
        "Date des données exportées : du {0} au {1}".format(
            min_date.strftime("%d/%m/%Y"), max_date.strftime("%d/%m/%Y")
        ),
        wb.add_format({"bold": True}),
    )
