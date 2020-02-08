from unittest import TestCase

from app import app, db
from config import TestConfig


class BaseTest(TestCase):
    def setUp(self):
        app.config.from_object(TestConfig)
        app.testing = True

    def tearDown(self) -> None:
        db.close_all_sessions()
        all_tables = [
            "public." + str(table)
            for table in reversed(db.metadata.sorted_tables)
        ]
        db.engine.execute("TRUNCATE {} CASCADE;".format(", ".join(all_tables)))
