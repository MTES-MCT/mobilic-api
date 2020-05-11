from collections import namedtuple
from freezegun import freeze_time
from datetime import datetime
from contextlib import contextmanager

import re

from app import app, db
from app.helpers.time import to_timestamp
from app.models import Activity, User

DBEntryUpdate = namedtuple("DBUnitUpdate", ["model", "before", "after"])
MatchingExpectedChangesWithDbDiff = namedtuple(
    "MatchingExpectedChangesWithDbDiff",
    ["matches", "uncommitted_updates", "unexpected_commits"],
)
ForeignKey = namedtuple("ForeignKey", ["foreign_object_name"])


def _camel_to_snake(obj):
    if type(obj) is dict:
        return {_camel_to_snake(k): v for k, v in obj.items()}
    if type(obj) is list:
        return [_camel_to_snake(item) for item in obj]
    else:
        return re.sub("(.)([A-Z][a-z]+)", r"\1_\2", str(obj)).lower()


def _snake_to_camel(obj):
    if type(obj) is dict:
        return {_snake_to_camel(k): v for k, v in obj.items()}
    if type(obj) is list:
        return [_snake_to_camel(item) for item in obj]
    else:
        first_word, *rest = str(obj).split("_")
        return first_word + "".join(word.title() for word in rest)


def _convert_date_time_to_timestamps(obj):
    if type(obj) is dict:
        return {k: _convert_date_time_to_timestamps(v) for k, v in obj.items()}
    if type(obj) is list:
        return [_convert_date_time_to_timestamps(item) for item in obj]
    if type(obj) is datetime:
        return to_timestamp(obj)
    return obj


def _db_event_to_dict(obj):
    exclude_fields = ["revised_by", "_sa_instance_state", "activities"]
    return {k: v for k, v in obj.__dict__.items() if k not in exclude_fields}


def _remove_foreign_keys(obj):
    return {k: v for k, v in obj.items() if type(v) is not ForeignKey}


def _equals_on_intersect(d1, d2):
    if d1 is None or d2 is None:
        return d1 == d2
    d1_ = _remove_foreign_keys(d1)
    d2_ = _remove_foreign_keys(d2)
    return all([d2_[k] == d1_[k] for k in d1_ if k in d2_])


class ApiRequests:
    log_activity = """
        mutation ($type: InputableActivityTypeEnum!, $eventTime: DateTimeWithTimeStampSerialization!, $userTime: DateTimeWithTimeStampSerialization, $missionId: Int, $driver: TeamMateInput) {
            logActivity (type: $type, eventTime: $eventTime, missionId: $missionId, driver: $driver, userTime: $userTime) {
                missionActivities
                 {
                    id
                    type
                }
            }
        }
    """
    begin_mission = """
        mutation ($firstActivityType: InputableActivityTypeEnum!, $name: String, $eventTime: DateTimeWithTimeStampSerialization!, $team: [TeamMateInput], $vehicleId: Int, $vehicleRegistrationNumber: String) {
            beginMission (firstActivityType: $firstActivityType, name: $name, eventTime: $eventTime, team: $team, vehicleId: $vehicleId, vehicleRegistrationNumber: $vehicleRegistrationNumber) {
                mission
                 {
                    id
                    name
                }
            }
        }
    """
    end_mission = """
        mutation ($missionId: Int, $eventTime: DateTimeWithTimeStampSerialization!, $expenditures: GenericScalar) {
            endMission (missionId: $missionId, eventTime: $eventTime, expenditures: $expenditures) {
                mission
                 {
                    id
                    name
                }
            }
        }
    """
    edit_activity = """
        mutation ($activityId: Int!, $eventTime: DateTimeWithTimeStampSerialization!, $userTime: DateTimeWithTimeStampSerialization, $dismiss: Boolean!, $comment: String) {
            editActivity (activityId: $activityId, eventTime: $eventTime, userTime: $userTime, dismiss: $dismiss, comment: $comment) {
                missionActivities
                 {
                    id
                    type
                }
            }
        }
    """


def _compute_db_model_table_diff(model, old_table_entries, new_table_entries):
    actual_db_updates = []
    for oe in old_table_entries:
        if oe["id"] not in [ne["id"] for ne in new_table_entries]:
            actual_db_updates.append(
                DBEntryUpdate(model=model, before=oe, after=None)
            )
    for ne in new_table_entries:
        matching_old_entries = [
            oe for oe in old_table_entries if oe["id"] == ne["id"]
        ]
        matching_old_entry = (
            matching_old_entries[0] if matching_old_entries else None
        )
        if matching_old_entry != ne:
            actual_db_updates.append(
                DBEntryUpdate(model=model, before=matching_old_entry, after=ne)
            )
    return actual_db_updates


def _match_expected_updates_with_db_diff(expected_db_updates, actual_db_diff):
    matching = {}
    remaining_expected_updates = {**expected_db_updates}
    for expected_update_name, expected_update in expected_db_updates.items():
        actual_updates_on_the_same_object = [
            db_upd
            for db_upd in actual_db_diff
            if db_upd.model == expected_update.model
            and _equals_on_intersect(expected_update.before, db_upd.before)
        ]
        if actual_updates_on_the_same_object:
            if expected_update.before:
                assert (
                    len(actual_updates_on_the_same_object) <= 1
                ), f"Ambiguous update target {expected_update.before} is referring to multiple db entries"
            update_matches = [
                db_upd
                for db_upd in actual_updates_on_the_same_object
                if _equals_on_intersect(expected_update.after, db_upd.after)
            ]
            if update_matches:
                if expected_update.after:
                    assert (
                        len(update_matches) <= 1
                    ), f"Ambiguous update target {expected_update.after} is referring to multiple db entries"
                matching[expected_update_name] = update_matches[0]
                remaining_expected_updates.pop(expected_update_name)
                actual_db_diff.remove(update_matches[0])
    return MatchingExpectedChangesWithDbDiff(
        matches=matching,
        uncommitted_updates=remaining_expected_updates,
        unexpected_commits=actual_db_diff,
    )


@contextmanager
def test_db_changes(expected_changes, watch_models):
    if type(expected_changes) is list:
        expected_changes = {
            str(idx): item for idx, item in enumerate(expected_changes)
        }
    # 1. Query db to get state before the action
    old_db_state = {
        model: [_db_event_to_dict(entry) for entry in model.query.all()]
        for model in watch_models
    }
    db.session.rollback()

    try:
        yield None
        # 2. Do the actual stuff that will impact the db
    finally:
        # 3. Query the db again to get the new state
        db.session.rollback()
        new_db_state = {
            model: [_db_event_to_dict(entry) for entry in model.query.all()]
            for model in watch_models
        }
        db.session.rollback()

        actual_db_diff = []
        for model in watch_models:
            actual_db_diff += _compute_db_model_table_diff(
                model, old_db_state[model], new_db_state[model]
            )

        match_db_changes_result = _match_expected_updates_with_db_diff(
            expected_changes, actual_db_diff
        )
        if match_db_changes_result.uncommitted_updates:
            print("The following expected changes did not happen !")
            print(match_db_changes_result.uncommitted_updates)
        if match_db_changes_result.unexpected_commits:
            print("Unexpected changes to database !")
            print(match_db_changes_result.unexpected_commits)

        assert (
            len(match_db_changes_result.uncommitted_updates.items())
            + len(match_db_changes_result.unexpected_commits)
            == 0
        )

        for expected_change_name, expected_change in expected_changes.items():
            if expected_change.after:
                for field, value in expected_change.after.items():
                    if type(value) is ForeignKey:
                        assert (
                            match_db_changes_result.matches[
                                expected_change_name
                            ].after[field]
                            == match_db_changes_result.matches[
                                value.foreign_object_name
                            ].after["id"]
                        )


def make_authenticated_request(
    time, submitter_id, query, variables, request_should_fail_with=None
):
    formatted_variables = _snake_to_camel(
        _convert_date_time_to_timestamps(variables)
    )
    with freeze_time(time):
        with app.test_client(
            mock_authentication_with_user=User.query.get(submitter_id)
        ) as c:
            response = c.post_graphql(
                query=query, variables=formatted_variables,
            )
    db.session.rollback()

    if request_should_fail_with:
        if type(request_should_fail_with) is dict:
            status = request_should_fail_with.get("status")
            if status:
                assert response.status_code == status
    else:
        assert response.status_code == 200

    return response.json
