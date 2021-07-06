import argparse
from datetime import datetime

from app.domain.work_days import group_user_missions_by_day
from app.helpers.google_drive import auth_to_google_sheets
from app.models.activity import ActivityType
from app.models.expenditure import ExpenditureType
from app.models.queries import user_query_with_all_relations


def load_users(limit=None):
    return user_query_with_all_relations().limit(limit).all()


def compute_usage_stats(users):
    # Get all missions of a user
    user_missions = {}
    for u in users:
        user_missions[u] = set()
        for a in u.activities:
            user_missions[u].add(a.mission)

    # Build work days from user missions
    user_work_days = {}
    for user, missions in user_missions.items():
        work_days = group_user_missions_by_day(user, missions)

        ## Augment work days with additional info
        for wd in work_days:
            wd.logged_entirely_by_user = all(
                [a.submitter_id == wd.user.id for a in wd._all_activities]
            )
            wd.logged_partially_by_user = any(
                [a.submitter_id == wd.user.id for a in wd._all_activities]
            )
            activity_switch_times = [a.start_time for a in wd.activities]
            for a in wd.activities:
                if a.end_time and a.end_time not in activity_switch_times:
                    activity_switch_times.append(a.end_time)
            revision_times = {
                av.reception_time
                for a in wd._all_activities
                for av in a.revisions
            }
            dismiss_times = {
                a.dismissed_at
                for a in wd._all_activities
                if a.dismissed_at is not None
            }
            all_times = revision_times | dismiss_times
            wd.n_activities = len(activity_switch_times) - 1
            wd.n_activity_events = len(all_times)

        user_work_days[user] = work_days

    work_day_stats = []
    for user, wds in user_work_days.items():
        primary_company = user.primary_company
        work_day_stats.append(
            {
                "Identifiant": str(user.id),
                "Prénom": user.first_name,
                "Nom": user.last_name,
                "Entreprise": primary_company.name
                if primary_company
                else None,
                **_compute_work_days_stats(wds),
            }
        )

    return work_day_stats


def _datetime_to_gsheet_format(dt):
    return (dt.timestamp() - datetime(1899, 12, 30).timestamp()) / 86400.0


def _compute_work_days_stats(wds):
    complete_wds = [w for w in wds if w.is_complete]
    return {
        "n_work_days": len(wds),
        "Journées de travail totales": len(complete_wds),
        "Journées de travail enregistrées par lui-même": len(
            [w for w in complete_wds if w.logged_entirely_by_user]
        ),
        "n_work_days_partially_logged_by_self": len(
            [w for w in complete_wds if w.logged_partially_by_user]
        ),
        "Date de la première journée enregistrée": _datetime_to_gsheet_format(
            min([w.start_time for w in complete_wds if w.start_time])
        )
        if complete_wds
        else None,
        "Date de la dernière journée enregistrée": _datetime_to_gsheet_format(
            max([w.start_time for w in complete_wds if w.start_time])
        )
        if complete_wds
        else None,
        "Durée moyenne du service": sum(
            [w.service_duration for w in complete_wds]
        )
        / 86400.0
        / len(complete_wds)
        if complete_wds
        else None,
        **{
            f"avg_{t.value if type(t) is not str else t}_activity_duration": round(
                sum([w.activity_durations.get(t, 0) for w in complete_wds])
                / len(complete_wds)
            )
            if complete_wds
            else None
            for t in ActivityType._member_map_.values()
        },
        "Durée moyenne du travail": sum(
            [w.total_work_duration for w in complete_wds]
        )
        / 86400.0
        / len(complete_wds)
        if complete_wds
        else None,
        "Nombre moyen d'activités par jour": round(
            sum([w.n_activities for w in complete_wds]) / len(complete_wds), 1,
        )
        if complete_wds
        else None,
        "Nombre moyen de missions": round(
            sum([len(w.missions) for w in complete_wds]) / len(complete_wds), 1
        )
        if complete_wds
        else None,
        "Nombre moyen d'actions d'enregistrement dans l'outil par jour": round(
            sum([w.n_activity_events for w in complete_wds])
            / len(complete_wds),
            1,
        )
        if complete_wds
        else None,
        **{
            f"avg_{t.value}_expenditures": sum(
                [w.expenditures.get(t, 0) for w in complete_wds]
            )
            / len(complete_wds)
            if complete_wds
            else None
            for t in ExpenditureType._member_map_.values()
        },
    }


light_green_color = {"red": 39, "green": 22, "blue": 45}


COLUMNS = {
    "Identifiant": {},
    "Prénom": {},
    "Nom": {},
    "Entreprise": {},
    "Journées de travail totales": {
        "type": "NUMBER",
        "background": light_green_color,
    },
    "Journées de travail enregistrées par lui-même": {
        "type": "NUMBER",
        "background": light_green_color,
    },
    "Date de la première journée enregistrée": {
        "type": "DATE",
        "pattern": "dd/mm/yyyy",
    },
    "Date de la dernière journée enregistrée": {
        "type": "DATE",
        "pattern": "dd/mm/yyyy",
    },
    "Durée moyenne du service": {"type": "DATE_TIME", "pattern": "[hh]:mm"},
    "Durée moyenne du travail": {"type": "DATE_TIME", "pattern": "[hh]:mm"},
    "Nombre moyen d'activités par jour": {
        "type": "NUMBER",
        "pattern": "#.0",
        "note": "Nombre d'activités qui composent la journée, en incluant les temps de pause.\nExemples :\n - conduite, travail, pause, travail, conduite -> 5\n - travail, pause, travail -> 3",
    },
    "Nombre moyen d'actions d'enregistrement dans l'outil par jour": {
        "type": "NUMBER",
        "pattern": "#.0",
        "background": light_green_color,
        "note": "Nombre d'actions effectuées dans l'application qui concernent le temps de travail :\n - changement d'activité en temps réel\n - ajout d'une activité a posteriori\n - correction d'une activité\n - suppression d'une activité\n - fin de journée\n. Dans le cas d'une saisie uniquement en temps réel, ce devrait être égal au nombre d'activités de la journée + 1 (action de fin de journée).",
    },
}


def compute_and_write_usage_stats(path="data/user_stats.csv"):
    users = load_users()
    work_day_stats = compute_usage_stats(users)
    work_day_stats_with_clean_columns = [
        {k: wd[k] for k in COLUMNS} for wd in work_day_stats
    ]
    df = pd.DataFrame.from_records(work_day_stats_with_clean_columns)
    df.to_csv(path, index=False, sep="\t", decimal=",")


SPREADSHEET_ID = "1MMlY1cpxhaFDueuXehQcnAh5bzZI8fyBKEOk7B7nxGk"


def add_new_sheet(sheets, date, work_days):

    timestamp = datetime(date.year, date.month, date.day).timestamp()
    return sheets.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "sheetId": timestamp,
                            "title": date.strftime("%d/%m/%Y"),
                            "index": 0,
                            "gridProperties": {"frozenRowCount": 1},
                        }
                    }
                },
                {
                    "appendCells": {
                        "sheetId": timestamp,
                        "fields": "*",
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {
                                            "stringValue": column
                                        },
                                        "userEnteredFormat": {
                                            "textFormat": {"bold": True},
                                            "verticalAlignment": "BOTTOM",
                                            "wrapStrategy": "WRAP",
                                            "backgroundColor": props.get(
                                                "background"
                                            ),
                                        },
                                        "note": props.get("note"),
                                    }
                                    for column, props in COLUMNS.items()
                                ]
                            },
                            *[
                                {
                                    "values": [
                                        {
                                            "userEnteredValue": {
                                                "numberValue"
                                                if props.get("type")
                                                in [
                                                    "NUMBER",
                                                    "DATE_TIME",
                                                    "DATE",
                                                ]
                                                else "stringValue": wd[column]
                                            },
                                            "userEnteredFormat": {
                                                "wrapStrategy": "WRAP",
                                                "backgroundColor": props.get(
                                                    "background"
                                                ),
                                                "numberFormat": {
                                                    "type": props.get(
                                                        "type", "TEXT"
                                                    ),
                                                    "pattern": props.get(
                                                        "pattern"
                                                    ),
                                                },
                                            },
                                        }
                                        for column, props in COLUMNS.items()
                                    ]
                                }
                                for wd in work_days
                            ],
                        ],
                    }
                },
                {
                    "setBasicFilter": {
                        "filter": {
                            "sortSpecs": {
                                "sortOrder": "DESCENDING",
                                "dimensionIndex": 5,
                            },
                            "range": {"sheetId": timestamp},
                        }
                    }
                },
            ]
        },
    ).execute()


def compute_and_add_usage_stats_snapshot():
    # Compute stats
    users = load_users()
    work_day_stats = compute_usage_stats(users)

    today = datetime.now().date()

    # Auth to gsheets API
    sheets = auth_to_google_sheets()
    return add_new_sheet(sheets, today, work_day_stats)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--only_sundays",
    help="Only run if current day is Sunday",
    action="store_true",
)


if __name__ == "__main__":
    args = parser.parse_args()
    today = datetime.now().date()
    if not args.only_sundays or today.weekday() == 6:
        compute_and_add_usage_stats_snapshot()
