from app.helpers.xls.common import red_hex, white_hex


def write_sheet_header(
    wb, sheet, companies, max_date, min_date, deleted_missions=False
):
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
    if deleted_missions:
        sheet.merge_range(
            2,
            0,
            2,
            2,
            "Une mission est supprimée lorsque toutes les activités ont été supprimées",
            wb.add_format(
                {
                    "bold": True,
                    "bg_color": red_hex,
                    "color": white_hex,
                    "text_wrap": False,
                }
            ),
        )
        return 4
    else:
        return 3
