from app import db


class IdMapping(db.Model):
    """
    Model for tracking mappings between original and anonymized entity IDs.

    This table is used during the anonymization process to:
    1. Map original entity IDs to their anonymized counterparts
    2. Track which entities are targets for deletion vs. which are only referenced
    """

    __tablename__ = "temp_id_mapping"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)
    original_id = db.Column(db.Integer, nullable=False)
    anonymized_id = db.Column(db.Integer, nullable=False)
    deletion_target = db.Column(
        db.Boolean, default=False, nullable=False, index=True
    )

    __table_args__ = (
        db.UniqueConstraint(
            "entity_type", "original_id", name="uix_entity_original"
        ),
        db.UniqueConstraint(
            "entity_type", "anonymized_id", name="uix_entity_anonymized"
        ),
    )
