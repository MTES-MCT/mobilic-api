from app import db
from app.models.base import BaseModel


class SoftwareComplianceAlertState(BaseModel):
    __tablename__ = "software_compliance_alert_state"

    client_id = db.Column(
        db.Integer,
        db.ForeignKey("oauth2_client.id"),
        index=True,
        nullable=False,
    )
    metric = db.Column(db.String, nullable=False)
    last_alerted_on = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "client_id",
            "metric",
            name="uq_software_compliance_alert_state_client_metric",
        ),
    )
