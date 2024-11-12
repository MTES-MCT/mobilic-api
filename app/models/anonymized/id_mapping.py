from app import db


class IdMapping(db.Model):
    __tablename__ = "temp_id_mapping"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50))
    original_id = db.Column(db.Integer)
    anonymized_id = db.Column(db.Integer)

    __table_args__ = (
        db.UniqueConstraint(
            "entity_type", "original_id", name="uix_entity_original"
        ),
        db.UniqueConstraint(
            "entity_type", "anonymized_id", name="uix_entity_anonymized"
        ),
    )
