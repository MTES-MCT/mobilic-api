from app import db
from datetime import datetime
from sqlalchemy.orm.exc import MultipleResultsFound
from app.models.anonymized import AnonymizedModel, IdMapping
from app.tests.helpers import test_db_changes, DBEntryUpdate


class TestAnonymizedModel:
    def test_get_new_id_creates_mapping(self):
        """Test la création d'un nouveau mapping"""
        entity_type = "test_entity"
        original_id = 1

        with test_db_changes(
            {
                "mapping": DBEntryUpdate(
                    model=IdMapping,
                    before=None,
                    after={
                        "entity_type": entity_type,
                        "original_id": original_id,
                    },
                )
            },
            watch_models=[IdMapping],
        ):
            new_id = AnonymizedModel.get_new_id(entity_type, original_id)

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).one_or_none()
        assert mapping is not None
        assert mapping.anonymized_id == new_id

    def test_get_new_id_returns_existing(self):
        """Test la récupération d'un mapping existant"""
        entity_type = "test_entity"
        original_id = 1
        anonymized_id = 100

        mapping = IdMapping(
            entity_type=entity_type,
            original_id=original_id,
            anonymized_id=anonymized_id,
        )
        db.session.add(mapping)
        db.session.commit()

        result = AnonymizedModel.get_new_id(entity_type, original_id)
        assert result == anonymized_id

    def test_duplicate_mapping_raises(self):
        """Test la gestion des mappings dupliqués"""
        entity_type = "test_entity"
        original_id = 1

        mappings = [
            IdMapping(
                entity_type=entity_type,
                original_id=original_id,
                anonymized_id=100,
            ),
            IdMapping(
                entity_type=entity_type,
                original_id=original_id,
                anonymized_id=200,
            ),
        ]
        db.session.add_all(mappings)
        db.session.commit()

        try:
            AnonymizedModel.get_new_id(entity_type, original_id)
            assert False, "Une exception aurait dû être levée"
        except MultipleResultsFound:
            pass
        except Exception as e:
            assert False, f"Mauvais type d'exception : {type(e)}"

    def test_truncate_to_month_datetime(self):
        """Test que la troncature au mois fonctionne pour un datetime"""
        test_date = datetime(2024, 2, 15, 14, 30, 45)
        truncated = AnonymizedModel.truncate_to_month(test_date)

        assert truncated.year == 2024
        assert truncated.month == 2
        assert truncated.day == 1
        assert truncated.hour == 0
        assert truncated.minute == 0
        assert truncated.second == 0
        assert truncated.microsecond == 0

    def test_truncate_to_month_date(self):
        """Test que la troncature au mois fonctionne pour une date"""
        test_date = datetime(2024, 2, 15).date()
        truncated = AnonymizedModel.truncate_to_month(test_date)

        assert truncated.year == 2024
        assert truncated.month == 2
        assert truncated.day == 1
