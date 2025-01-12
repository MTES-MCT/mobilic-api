from app import db
from .id_mapping import IdMapping
import uuid


class AnonymizedModel(db.Model):
    __abstract__ = True

    @staticmethod
    def get_new_id(entity_type: str, old_id: int):
        if old_id is None:
            return None

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=old_id
        ).first()

        if mapping is None:
            # Compute modulo with 2^31 to ensure the generated ID fits within PostgreSQL INTEGER range (-2^31 to 2^31-1)
            new_id = uuid.uuid4().int % (2**31)
            mapping = IdMapping(
                entity_type=entity_type,
                original_id=old_id,
                anonymized_id=new_id,
            )
            db.session.add(mapping)
            db.session.flush()

        return mapping.anonymized_id

    @staticmethod
    def truncate_to_month(date):
        if date is None:
            return None
        return date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
