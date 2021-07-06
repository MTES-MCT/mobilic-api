from app.helpers.google_drive import auth_to_google_sheets


SPREADSHEET_ID = "1NoaV9DKYXt5Uwy_P-53iGNYiJoRZe8RpxAEsg7GG9Ag"
DEFAULT_HEADER_INDEX = 3
COLUMNS = [
    {
        "name": "Nom entreprise",
        "value": lambda company, user: company.name,
        "default_index": 0,
    },
    {
        "name": "Contact",
        "value": lambda company, user: user.display_name,
        "default_index": 1,
    },
    {
        "name": "Mail contact",
        "value": lambda company, user: user.email,
        "default_index": 2,
    },
    {
        "name": "Date d'inscription",
        "value": lambda company, user: company.creation_time.strftime(
            "%d/%m/%y"
        ),
        "default_index": 3,
    },
    {
        "name": "Lien Metabase",
        "value": lambda company, user: f"https://metabase.mobilic.beta.gouv.fr/dashboard/3?id={company.id}",
    },
    {"name": "ID", "value": lambda company, user: company.id,},
]


def add_company_to_spreadsheet(company, admin):
    sheets = auth_to_google_sheets()
    # Find the header column
    first_rows = (
        sheets.values()
        .get(spreadsheetId=SPREADSHEET_ID, range="A1:Z10")
        .execute()
    )
    header_index = -1
    for index, row in enumerate(first_rows["values"]):
        if row and row[0] == "Nom entreprise":
            header_index = index
            break

    header_column_length = 0
    if header_index >= 0:
        header_names = first_rows["values"][header_index]
        header_column_length = len(header_names)

        columns = [dict(**c) for c in COLUMNS]

        for col in columns:
            matching_colindexes = [
                i
                for i in range(header_column_length)
                if header_names[i] == col["name"]
            ]
            col["index"] = (
                matching_colindexes[0]
                if matching_colindexes
                else col.get("default_index", None)
            )

    new_row_index = (
        header_index + 1 if header_index >= 0 else DEFAULT_HEADER_INDEX + 1
    )

    # Append the new company on top of the table (right below header column)
    requests = [
        {
            "insertDimension": {
                "range": {
                    "sheetId": 0,
                    "dimension": "ROWS",
                    "startIndex": new_row_index,
                    "endIndex": new_row_index + 1,
                },
                "inheritFromBefore": False,
            }
        }
    ]

    for col in columns:
        if col.get("index", None) is not None:
            requests.append(
                {
                    "updateCells": {
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {
                                            "stringValue": str(
                                                col["value"](company, admin)
                                            )
                                        }
                                    }
                                ]
                            }
                        ],
                        "fields": "userEnteredValue",
                        "start": {
                            "sheetId": 0,
                            "rowIndex": new_row_index,
                            "columnIndex": col["index"],
                        },
                    }
                }
            )

    requests.append(
        {
            "copyPaste": {
                "source": {
                    "sheetId": 0,
                    "startRowIndex": new_row_index + 1,
                    "endRowIndex": new_row_index + 2,
                    "startColumnIndex": 0,
                    "endColumnIndex": header_column_length + 1,
                },
                "destination": {
                    "sheetId": 0,
                    "startRowIndex": new_row_index,
                    "endRowIndex": new_row_index + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": header_column_length + 1,
                },
                "pasteType": "PASTE_FORMAT",
                "pasteOrientation": "NORMAL",
            }
        }
    )
    sheets.batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body={"requests": requests},
    ).execute()
