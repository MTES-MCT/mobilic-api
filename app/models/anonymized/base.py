from app import db
from .id_mapping import IdMapping


class AnonymizedModel(db.Model):
    __abstract__ = True

    @classmethod
    def get_new_id(cls, entity_type: str, old_id: int):
        if old_id is None:
            return None

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=old_id
        ).first()

        if mapping is not None:
            return mapping.anonymized_id

        result = db.session.execute("SELECT nextval('anonymized_id_seq')")
        new_id = result.scalar()

        mapping = IdMapping(
            entity_type=entity_type, original_id=old_id, anonymized_id=new_id
        )
        db.session.add(mapping)

        db.session.flush()
        db.session.refresh(mapping)

        return new_id

    @staticmethod
    def truncate_to_month(date):
        if date is None:
            return None
        if hasattr(date, "hour"):
            return date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        return date.replace(day=1)
