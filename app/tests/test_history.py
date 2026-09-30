from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase

from app.domain.history import (
    LogActionType,
    UserChange,
    _ctx_get,
    _is_split,
)
from app.models.activity import Activity, ActivityType

# `context` is a free-form field a partner API call can fill with any JSON
# value. It used to be assumed to always be a dict, which crashed
# `_is_split`/`is_support`/`motif` with
# `AttributeError: 'str' object has no attribute 'get'`.
NON_DICT_CONTEXT = "zxq8f-random-string-payload-4821"


def _version(context):
    return SimpleNamespace(
        context=context,
        start_time=datetime(2026, 9, 20, 8, 0),
        end_time=datetime(2026, 9, 20, 10, 0),
    )


def _activity():
    activity = Activity()
    activity.type = ActivityType.DRIVE
    return activity


class TestCtxGet(TestCase):
    def test_returns_value_for_dict(self):
        self.assertEqual(_ctx_get({"splitFrom": 42}, "splitFrom"), 42)

    def test_returns_none_for_missing_key(self):
        self.assertIsNone(_ctx_get({"other": 1}, "splitFrom"))

    def test_returns_none_for_none(self):
        self.assertIsNone(_ctx_get(None, "splitFrom"))

    def test_returns_none_for_empty_dict(self):
        self.assertIsNone(_ctx_get({}, "splitFrom"))

    def test_returns_none_and_logs_warning_for_non_dict_string(self):
        with self.assertLogs("app.domain.history", level="WARNING") as logs:
            result = _ctx_get(NON_DICT_CONTEXT, "splitFrom")
        self.assertIsNone(result)
        self.assertIn("splitFrom", logs.output[0])

    def test_returns_none_and_logs_warning_for_non_dict_list(self):
        with self.assertLogs("app.domain.history", level="WARNING"):
            result = _ctx_get(["splitFrom"], "splitFrom")
        self.assertIsNone(result)

    def test_does_not_log_for_falsy_non_dict(self):
        with self.assertNoLogs("app.domain.history", level="WARNING"):
            self.assertIsNone(_ctx_get("", "splitFrom"))


class TestIsSplit(TestCase):
    def test_true_when_split_from_present(self):
        version = _version({"splitFrom": 123})
        self.assertTrue(_is_split(version))

    def test_false_when_no_context(self):
        version = _version(None)
        self.assertFalse(_is_split(version))

    def test_false_when_version_is_none(self):
        self.assertFalse(_is_split(None))

    def test_false_and_no_crash_when_context_is_a_string(self):
        version = _version(NON_DICT_CONTEXT)
        with self.assertLogs("app.domain.history", level="WARNING"):
            result = _is_split(version)
        self.assertFalse(result)


class TestHistoryItemIsSupport(TestCase):
    def _change(self, version=None, resource=None, type=LogActionType.CREATE):
        return UserChange(
            time=datetime(2026, 9, 20, 8, 0),
            submitter=None,
            submitter_has_admin_rights=False,
            is_after_employee_validation=False,
            resource=resource if resource is not None else _activity(),
            type=type,
            version=version,
        )

    def test_true_when_dict_context_has_is_support(self):
        change = self._change(version=_version({"is_support": True}))
        self.assertTrue(change.is_support)

    def test_false_when_no_context(self):
        change = self._change(version=_version(None))
        self.assertFalse(change.is_support)

    def test_false_and_no_crash_when_context_is_not_a_dict(self):
        change = self._change(version=_version(NON_DICT_CONTEXT))
        with self.assertLogs("app.domain.history", level="WARNING"):
            result = change.is_support
        self.assertFalse(result)


class TestUserChangeMotif(TestCase):
    def _change(self, version):
        return UserChange(
            time=datetime(2026, 9, 20, 8, 0),
            submitter=None,
            submitter_has_admin_rights=False,
            is_after_employee_validation=False,
            resource=_activity(),
            type=LogActionType.CREATE,
            version=version,
        )

    def test_returns_user_comment_for_dict_context(self):
        change = self._change(
            _version({"userComment": "raison du changement"})
        )
        self.assertEqual(change.motif, "raison du changement")

    def test_returns_none_and_no_crash_when_context_is_not_a_dict(self):
        change = self._change(_version(NON_DICT_CONTEXT))
        with self.assertLogs("app.domain.history", level="WARNING"):
            result = change.motif
        self.assertIsNone(result)


class TestUserChangeTextsSplitActivity(TestCase):
    def _change(self, version):
        return UserChange(
            time=datetime(2026, 9, 20, 8, 0),
            submitter=None,
            submitter_has_admin_rights=False,
            is_after_employee_validation=False,
            resource=_activity(),
            type=LogActionType.CREATE,
            version=version,
        )

    def test_no_crash_when_split_context_is_not_a_dict(self):
        # Regression test for the Sentry AttributeError that blocked
        # mission auto-validation: `_is_split` used to raise when
        # `version.context` was a non-dict truthy value.
        change = self._change(_version(NON_DICT_CONTEXT))
        with self.assertLogs("app.domain.history", level="WARNING"):
            texts = change.texts()
        self.assertEqual(len(texts), 1)
        self.assertIn("Conduite", texts[0])
