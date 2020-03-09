from collections import namedtuple
from freezegun import freeze_time
from unittest import TestCase
from datetime import datetime
import re

from app import app, db
from app.models import Activity, User

DBUnitUpdate = namedtuple("DBUnitUpdate", ["before", "after"])


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


def _equals_on_intersect(d1, d2):
    if d1 is None or d2 is None:
        return d1 == d2
    return all([d2[k] == d1[k] for k in d1 if k in d2])


class DBEventChange:
    def __init__(self, unit_updates):
        self.unit_updates = unit_updates

    @staticmethod
    def _get_db_diff(old_events, new_events):
        actual_db_updates = []
        for oe in old_events:
            if oe["id"] not in [ne["id"] for ne in new_events]:
                actual_db_updates.append(DBUnitUpdate(before=oe, after=None))
        for ne in new_events:
            matching_old_events = [
                oe for oe in old_events if oe["id"] == ne["id"]
            ]
            matching_old_event = (
                matching_old_events[0] if matching_old_events else None
            )
            if matching_old_event != ne:
                actual_db_updates.append(
                    DBUnitUpdate(before=matching_old_event, after=ne)
                )
        return actual_db_updates

    def compare_with_db_diff(self, old_events, new_events):
        remaining_db_diff = self._get_db_diff(old_events, new_events)
        remaining_expected_updates = [*self.unit_updates]
        for expected_update in self.unit_updates:
            actual_updates_on_the_same_object = [
                db_upd
                for db_upd in remaining_db_diff
                if _equals_on_intersect(expected_update.before, db_upd.before)
            ]
            if actual_updates_on_the_same_object:
                if expected_update.before:
                    assert (
                        len(actual_updates_on_the_same_object) <= 1
                    ), f"Ambiguous update target {expected_update.before} is referring to multiple db entries"
                update_matches = [
                    db_upd
                    for db_upd in actual_updates_on_the_same_object
                    if _equals_on_intersect(
                        expected_update.after, db_upd.after
                    )
                ]
                if update_matches:
                    if expected_update.after:
                        assert (
                            len(update_matches) <= 1
                        ), f"Ambiguous update target {expected_update.after} is referring to multiple db entries"
                    remaining_expected_updates.remove(expected_update)
                    remaining_db_diff.remove(update_matches[0])
        return remaining_expected_updates, remaining_db_diff

    def __add__(self, other):
        composed_unit_updates = [*self.unit_updates]
        if type(other) is DBUnitUpdate:
            other = DBEventChange([other])
        for new_update in other.unit_updates:
            matching_previous_updates = [
                upd
                for upd in composed_unit_updates
                if _equals_on_intersect(upd.after, new_update.before)
                and upd.after is not None
            ]
            if matching_previous_updates:
                assert (
                    len(matching_previous_updates) <= 1
                ), "Cannot compose db event changes : one of the newer unit changes is ambiguously referring to several of the old changes"
                composed_unit_updates.remove(matching_previous_updates[0])
                new_update = DBUnitUpdate(
                    before=matching_previous_updates[0].before,
                    after=new_update.after,
                )
            if new_update.before or new_update.after:
                composed_unit_updates.append(new_update)

        return DBEventChange(composed_unit_updates)


EVENT_SUBMIT_OPERATIONS = {
    "log_activities": {
        "model": Activity,
        "query": """
                mutation ($data: [SingleActivityInput]!) {
                    logActivities (data: $data) {
                        activities {
                            id
                            type
                            startTime
                        }
                    }
                }
            """,
    },
    "cancel_activities": {
        "model": Activity,
        "query": """
                mutation($data: [CancelEventInput]!) {
                    cancelActivities(data: $data) {
                        activities {
                            id
                            type
                            startTime
                        }
                    }
                }
            """,
    },
    "revise_activities": {
        "model": Activity,
        "query": """
                mutation($data: [ActivityRevisionInput]!) {
                    reviseActivities(data: $data) {
                        activities {
                            id
                            type
                            startTime
                        }
                    }
                }
            """,
    },
}


class SubmitEventsTest:
    def __init__(
        self,
        operation_type,
        data,
        submitter,
        expected_db_event=DBEventChange([]),
        request_should_fail_with=None,
        submit_time=None,
    ):
        self.operation_type = operation_type
        operation_props = EVENT_SUBMIT_OPERATIONS[operation_type]
        self.query = operation_props["query"]
        self.event_model = operation_props["model"]
        self.submitter_id = submitter.id
        self.expected_db_event = expected_db_event
        self.data = data if type(data) is list else [data]
        self.request_should_fail_with = request_should_fail_with
        self.submit_time = submit_time or datetime.now()

    def test(self, test: TestCase):
        # 1. Query db to get state of events before the submit
        all_events_before_submit = [
            {k: v for k, v in a.__dict__.items() if k != "_sa_instance_state"}
            for a in self.event_model.query.all()
        ]

        db.session.rollback()

        # 2. Submit operation
        with freeze_time(self.submit_time):
            with app.test_client(
                mock_authentication_with_user=User.query.get(self.submitter_id)
            ) as c:
                response = c.post_graphql(
                    query=self.query,
                    variables=dict(data=_snake_to_camel(self.data)),
                )

        if self.request_should_fail_with:
            status = self.request_should_fail_with.get("status")
            if status:
                test.assertEqual(response.status_code, status)
        else:
            test.assertEqual(response.status_code, 200)

        db.session.rollback()

        # 3. Query again db to get state of events after the submit
        all_events_after_submit = [
            {k: v for k, v in a.__dict__.items() if k != "_sa_instance_state"}
            for a in self.event_model.query.all()
        ]

        db.session.rollback()

        (
            expected_changes_not_committed,
            unexpectedly_committed_changes,
        ) = self.expected_db_event.compare_with_db_diff(
            all_events_before_submit, all_events_after_submit
        )
        if expected_changes_not_committed:
            print("The following expected changes did not happen !")
            print(expected_changes_not_committed)
        if unexpectedly_committed_changes:
            print("Unexpected changes to database !")
            print(unexpectedly_committed_changes)
        test.assertTupleEqual(
            (expected_changes_not_committed, unexpectedly_committed_changes),
            ([], []),
        )

        # 4. Check response

    def should_create(self, **event_dict):
        self.expected_db_event += DBUnitUpdate(before=None, after=event_dict)
        return self

    def should_delete(self, **event_dict):
        self.expected_db_event += DBUnitUpdate(before=event_dict, after=None)
        return self

    def should_update(self, before, after):
        self.expected_db_event += DBUnitUpdate(before=before, after=after)
        return self

    def should_dismiss(self, **event_dict):
        dismiss_type = event_dict.get("dismiss_type")
        if not dismiss_type:
            raise ValueError(
                "Expected 'dismiss_type' argument to should_dismiss function"
            )

        before_event_dict = {**event_dict}
        before_event_dict.update(dismiss_type=None, dismissed_at=None)
        self.expected_db_event += DBUnitUpdate(
            before=before_event_dict, after=event_dict
        )
        return self

    def should_revise(self, before, after, revision_time):
        after["revised_at"] = None
        if after.get("dismiss_type"):
            after["dismissed_at"] = revision_time
        self.expected_db_event += DBUnitUpdate(
            before={**before, "revised_at": None},
            after={**before, "revised_at": revision_time},
        )
        self.expected_db_event += DBUnitUpdate(before=None, after=after)
        return self

    def add_event(self, data):
        self.data.append(data)
        return self


class SubmitEventsTestChain:
    def __init__(self, tests=None):
        self.tests = tests or []

    def __add__(self, other):
        self.tests.append(other)
        return self

    def test(self, test: TestCase):
        for single_test in self.tests:
            single_test.test(test)
