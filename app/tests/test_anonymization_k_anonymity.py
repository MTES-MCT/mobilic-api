from datetime import datetime, timedelta

from app import app, db
from app.models.anonymized import AnonActivity
from app.services.anonymization.utilities.k_anonymity import (
    apply_activity_k_anonymity,
)
from app.tests import BaseTest


class TestAnonymizationKAnonymity(BaseTest):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.app_context.pop()

    def test_k_anonymity_drops_users_with_unique_activity_count(self):
        base = datetime(2024, 1, 1)
        db.session.execute(AnonActivity.__table__.delete())
        rows = []
        for uid, count in [
            (-11, 2),
            (-12, 2),
            (-13, 2),
            (-14, 5),
        ]:
            for i in range(count):
                rows.append(
                    {
                        "id": abs(uid) * 100 + i,
                        "type": "drive",
                        "user_id": uid,
                        "submitter_id": uid,
                        "mission_id": abs(uid),
                        "creation_time": base,
                        "start_time": base,
                        "end_time": base + timedelta(minutes=30),
                        "last_update_time": base,
                    }
                )
        db.session.execute(AnonActivity.__table__.insert(), rows)
        db.session.commit()

        deleted = apply_activity_k_anonymity(k=2)

        self.assertEqual(deleted, 5)
        remaining_user_ids = {
            r[0]
            for r in db.session.query(AnonActivity.user_id).distinct().all()
        }
        self.assertEqual(remaining_user_ids, {-11, -12, -13})
