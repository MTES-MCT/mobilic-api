from app import db
from app.models.base import BaseModel


class SoftwareComplianceSnapshot(BaseModel):
    __tablename__ = "software_compliance_snapshot"

    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("oauth2_client.id"),
        index=True,
        nullable=False,
    )
    client_name = db.Column(db.String, nullable=False)

    nb_missions = db.Column(db.Integer, default=0, nullable=False)
    nb_activities = db.Column(db.Integer, default=0, nullable=False)
    pct_retroactive_gt4h = db.Column(db.Float, nullable=True)
    pct_retroactive_gt24h = db.Column(db.Float, nullable=True)
    pct_missing_start_loc = db.Column(db.Float, nullable=True)
    pct_missing_end_loc = db.Column(db.Float, nullable=True)
    pct_missing_vehicle = db.Column(db.Float, nullable=True)
    pct_missing_km_start = db.Column(db.Float, nullable=True)
    pct_missing_km_end = db.Column(db.Float, nullable=True)
    pct_auto_validation_only = db.Column(db.Float, nullable=True)
    pct_admin_modified = db.Column(db.Float, nullable=True)
    nb_controls = db.Column(db.Integer, nullable=True)
    pct_controls_with_qr_code = db.Column(db.Float, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "snapshot_date",
            "client_id",
            name="uq_software_compliance_snapshot_date_client",
        ),
    )
