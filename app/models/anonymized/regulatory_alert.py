from app import db
from .base import AnonymizedModel


DATETIME_KEYS_IN_EXTRA = (
    "breach_period_start",
    "breach_period_end",
    "work_range_start",
    "work_range_end",
    "longest_uninterrupted_work_end",
)


def _scrub_extra_datetimes(extra):
    if not isinstance(extra, dict):
        return extra
    scrubbed = dict(extra)
    for key in DATETIME_KEYS_IN_EXTRA:
        if key in scrubbed:
            scrubbed[key] = _truncate_iso_to_month(scrubbed[key])
    return scrubbed


def _truncate_iso_to_month(value):
    if not isinstance(value, str) or len(value) < 7:
        return value
    return f"{value[:7]}-01T00:00:00"


class AnonRegulatoryAlert(AnonymizedModel):
    __tablename__ = "anon_regulatory_alert"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    day = db.Column(db.Date, nullable=False)
    extra = db.Column(db.JSON, nullable=True)
    submitter_type = db.Column(db.String(length=50), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, alert):
        new_id = cls.get_new_id("regulatory_alert", alert.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.creation_time = cls.truncate_to_month(alert.creation_time)
        anonymized.day = cls.truncate_to_month(alert.day)
        anonymized.extra = _scrub_extra_datetimes(alert.extra)
        anonymized.submitter_type = alert.submitter_type
        anonymized.user_id = cls.get_new_id("user", alert.user_id)
        return anonymized
