from datetime import date, datetime, timedelta

from sqlalchemy import text

from app import app, db, mailer
from app.helpers.mail import MailjetMessage
from app.helpers.mail_type import EmailType
from app.helpers.tchap import send_tchap_message
from app.jobs import log_execution
from app.models.software_compliance_alert_state import (
    SoftwareComplianceAlertState,
)
from app.models.software_compliance_snapshot import SoftwareComplianceSnapshot

# Minimum missions per day to consider the day as "active" (avoids weekend noise)
MIN_MISSIONS_FOR_ACTIVE_DAY = 5

# Alert thresholds (values are percentages: 0–100)
THRESHOLDS = {
    "pct_retroactive_gt4h": (50.0, "Rétro-saisie >4h"),
    "pct_missing_start_loc": (30.0, "Missions sans localisation de départ"),
    "pct_missing_end_loc": (30.0, "Missions sans localisation de fin"),
    "pct_missing_vehicle": (30.0, "Missions sans véhicule"),
    "pct_auto_validation_only": (80.0, "Missions validées uniquement en auto"),
}

_METRICS_SQL = """
WITH client_missions AS (
  -- missions attribuées via les salariés rattachés au logiciel, pas toute l'entreprise
  SELECT DISTINCT
    oc.id        AS client_id,
    oc.name      AS client_name,
    m.id         AS mission_id,
    m.vehicle_id AS vehicle_id
  FROM oauth2_client oc
  JOIN third_party_client_employment tpce
    ON oc.id = tpce.client_id AND tpce.dismissed_at IS NULL
  JOIN employment e
    ON e.id = tpce.employment_id AND e.dismissed_at IS NULL
  JOIN activity a
    ON a.user_id = e.user_id AND a.dismissed_at IS NULL
  JOIN mission m ON m.id = a.mission_id
  WHERE m.reception_time >= :day_start
    AND m.reception_time < :day_end
),
act_stats AS (
  SELECT
    cm.client_id,
    cm.client_name,
    COUNT(DISTINCT cm.mission_id) AS nb_missions,
    COUNT(a.id)                   AS nb_activities,
    COUNT(CASE WHEN EXTRACT(EPOCH FROM (a.reception_time - a.start_time)) / 3600 > 4  THEN 1 END) AS retro_gt4h,
    COUNT(CASE WHEN EXTRACT(EPOCH FROM (a.reception_time - a.start_time)) / 3600 > 24 THEN 1 END) AS retro_gt24h
  FROM client_missions cm
  LEFT JOIN activity a ON a.mission_id = cm.mission_id AND a.dismissed_at IS NULL
  GROUP BY cm.client_id, cm.client_name
),
loc_stats AS (
  SELECT
    cm.client_id,
    COUNT(DISTINCT CASE WHEN le_s.id IS NULL THEN cm.mission_id END) AS no_start_loc,
    COUNT(DISTINCT CASE WHEN le_e.id IS NULL THEN cm.mission_id END) AS no_end_loc,
    COUNT(DISTINCT CASE WHEN cm.vehicle_id IS NULL THEN cm.mission_id END) AS no_vehicle,
    COUNT(DISTINCT CASE WHEN le_s.kilometer_reading IS NULL THEN cm.mission_id END) AS no_km_start,
    COUNT(DISTINCT CASE WHEN le_e.kilometer_reading IS NULL THEN cm.mission_id END) AS no_km_end
  FROM client_missions cm
  LEFT JOIN location_entry le_s
    ON le_s.mission_id = cm.mission_id AND le_s.type = 'mission_start_location'
  LEFT JOIN location_entry le_e
    ON le_e.mission_id = cm.mission_id AND le_e.type = 'mission_end_location'
  GROUP BY cm.client_id
),
val_stats AS (
  SELECT
    cm.client_id,
    COUNT(DISTINCT CASE WHEN NOT EXISTS (
      SELECT 1 FROM mission_validation mv2
      WHERE mv2.mission_id = cm.mission_id AND mv2.is_auto = FALSE
    ) THEN cm.mission_id END) AS auto_only_missions,
    COUNT(DISTINCT CASE WHEN EXISTS (
      SELECT 1 FROM mission_validation mv3
      WHERE mv3.mission_id = cm.mission_id
        AND mv3.is_admin = TRUE AND mv3.is_auto = FALSE
    ) THEN cm.mission_id END) AS admin_modified_missions
  FROM client_missions cm
  GROUP BY cm.client_id
),
controls_per_client AS (
  SELECT DISTINCT
    tpce.client_id,
    cc.id                        AS control_id,
    cc.qr_code_generation_time
  FROM controller_control cc
  JOIN employment e
    ON e.user_id = cc.user_id AND e.dismissed_at IS NULL
  JOIN third_party_client_employment tpce
    ON tpce.employment_id = e.id AND tpce.dismissed_at IS NULL
  WHERE cc.creation_time >= :day_start AND cc.creation_time < :day_end
),
controls_stats AS (
  SELECT
    client_id,
    COUNT(control_id)              AS nb_controls,
    COUNT(qr_code_generation_time) AS nb_controls_with_qr
  FROM controls_per_client
  GROUP BY client_id
)
SELECT
  a.client_id,
  a.client_name,
  a.nb_missions,
  a.nb_activities,
  ROUND(100.0 * a.retro_gt4h   / NULLIF(a.nb_activities, 0), 2) AS pct_retroactive_gt4h,
  ROUND(100.0 * a.retro_gt24h  / NULLIF(a.nb_activities, 0), 2) AS pct_retroactive_gt24h,
  ROUND(100.0 * l.no_start_loc / NULLIF(a.nb_missions, 0), 2)   AS pct_missing_start_loc,
  ROUND(100.0 * l.no_end_loc   / NULLIF(a.nb_missions, 0), 2)   AS pct_missing_end_loc,
  ROUND(100.0 * l.no_vehicle   / NULLIF(a.nb_missions, 0), 2)   AS pct_missing_vehicle,
  ROUND(100.0 * l.no_km_start  / NULLIF(a.nb_missions, 0), 2)   AS pct_missing_km_start,
  ROUND(100.0 * l.no_km_end    / NULLIF(a.nb_missions, 0), 2)   AS pct_missing_km_end,
  ROUND(100.0 * v.auto_only_missions      / NULLIF(a.nb_missions, 0), 2) AS pct_auto_validation_only,
  ROUND(100.0 * v.admin_modified_missions / NULLIF(a.nb_missions, 0), 2) AS pct_admin_modified,
  COALESCE(cs.nb_controls, 0)                                            AS nb_controls,
  ROUND(
    100.0 * COALESCE(cs.nb_controls_with_qr, 0)
    / NULLIF(COALESCE(cs.nb_controls, 0), 0),
  2)                                                                     AS pct_controls_with_qr_code
FROM act_stats a
JOIN loc_stats l ON l.client_id = a.client_id
JOIN val_stats v ON v.client_id = a.client_id
LEFT JOIN controls_stats cs ON cs.client_id = a.client_id
WHERE a.nb_missions > 0
"""


def _compute_and_store_snapshots(for_date):
    day_start = datetime.combine(for_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    rows = db.session.execute(
        text(_METRICS_SQL),
        {"day_start": day_start, "day_end": day_end},
    ).fetchall()

    def _f(v):
        return float(v) if v is not None else None

    snapshots = []
    for row in rows:
        existing = SoftwareComplianceSnapshot.query.filter_by(
            snapshot_date=for_date, client_id=row.client_id
        ).one_or_none()
        if existing:
            app.logger.warning(
                f"Snapshot for {row.client_name} on {for_date} already exists, skipping"
            )
            snapshots.append(existing)
            continue
        snapshot = SoftwareComplianceSnapshot(
            snapshot_date=for_date,
            client_id=row.client_id,
            client_name=row.client_name,
            nb_missions=row.nb_missions,
            nb_activities=row.nb_activities,
            pct_retroactive_gt4h=_f(row.pct_retroactive_gt4h),
            pct_retroactive_gt24h=_f(row.pct_retroactive_gt24h),
            pct_missing_start_loc=_f(row.pct_missing_start_loc),
            pct_missing_end_loc=_f(row.pct_missing_end_loc),
            pct_missing_vehicle=_f(row.pct_missing_vehicle),
            pct_missing_km_start=_f(row.pct_missing_km_start),
            pct_missing_km_end=_f(row.pct_missing_km_end),
            pct_auto_validation_only=_f(row.pct_auto_validation_only),
            pct_admin_modified=_f(row.pct_admin_modified),
            nb_controls=int(row.nb_controls) if row.nb_controls else 0,
            pct_controls_with_qr_code=_f(row.pct_controls_with_qr_code),
        )
        db.session.add(snapshot)
        snapshots.append(snapshot)

    db.session.commit()
    app.logger.info(
        f"Inserted {len(snapshots)} compliance snapshots for {for_date}"
    )
    return snapshots


def _count_consecutive_active_days_above_threshold(
    client_id, field, threshold, today
):
    """Counts consecutive active days (most recent first) where field > threshold."""
    snapshots = (
        SoftwareComplianceSnapshot.query.filter(
            SoftwareComplianceSnapshot.client_id == client_id,
            SoftwareComplianceSnapshot.snapshot_date < today,
            SoftwareComplianceSnapshot.nb_missions
            >= MIN_MISSIONS_FOR_ACTIVE_DAY,
        )
        .order_by(SoftwareComplianceSnapshot.snapshot_date.desc())
        .limit(200)
        .all()
    )
    consecutive = 0
    for snapshot in snapshots:
        value = getattr(snapshot, field)
        if value is not None and value > threshold:
            consecutive += 1
        else:
            break
    return consecutive


def _get_violations(client_id, today):
    # returns (violation_strings, triggered_fields) — triggered_fields used to persist alert state
    violations = []
    triggered_fields = []
    for field, (threshold, label) in THRESHOLDS.items():
        consecutive = _count_consecutive_active_days_above_threshold(
            client_id, field, threshold, today
        )
        if consecutive < 7:
            continue
        # alert on first week then re-alert every 7 days, robust to streak jumps and missed cron runs
        state = SoftwareComplianceAlertState.query.filter_by(
            client_id=client_id, metric=field
        ).one_or_none()
        if state and state.last_alerted_on > today - timedelta(days=7):
            continue
        window_start = today - timedelta(days=7)
        recent_days = SoftwareComplianceSnapshot.query.filter(
            SoftwareComplianceSnapshot.client_id == client_id,
            SoftwareComplianceSnapshot.snapshot_date >= window_start,
            SoftwareComplianceSnapshot.snapshot_date < today,
            SoftwareComplianceSnapshot.nb_missions
            >= MIN_MISSIONS_FOR_ACTIVE_DAY,
        ).all()
        values = [
            getattr(d, field)
            for d in recent_days
            if getattr(d, field) is not None
        ]
        avg_value = sum(values) / len(values) if values else 0
        week_number = consecutive // 7
        violations.append(
            f"- {label} : {avg_value:.1f}% "
            f"(seuil : {threshold}%, semaine {week_number} consécutive)"
        )
        triggered_fields.append(field)
    return violations, triggered_fields


def _send_consolidated_alert(alerts_by_client, today):
    if not alerts_by_client:
        return

    alert_email = app.config.get("COMPLIANCE_ALERT_EMAIL")
    nb = len(alerts_by_client)
    subject = f"[ALERTE WORKFLOW] {nb} logiciel(s) dépassent les seuils de conformité"
    sections_html = ""
    for client_name, client_id, violations in alerts_by_client:
        items_html = "".join(f"<li>{v.lstrip('- ')}</li>" for v in violations)
        sections_html += (
            f"<h3>{client_name} (client_id={client_id})</h3>"
            f"<ul>{items_html}</ul>"
        )
    html_body = f"""
    <h2>Résumé alertes conformité workflow — {today.strftime('%d/%m/%Y')}</h2>
    <p>{nb} logiciel(s) dépassent leurs seuils depuis 7 jours actifs consécutifs.</p>
    {sections_html}
    <p><em>Ces taux sont des estimations basées sur les salariés rattachés au logiciel, pas une attribution exacte par mission.</em></p>
    <p>Consultez le dashboard Metabase pour investiguer.</p>
    """

    if alert_email:
        msg = MailjetMessage(
            EmailType.SOFTWARE_COMPLIANCE_ALERT,
            subject=subject,
            recipient=alert_email,
            html=html_body,
        )
        mailer.send_batch([msg])
        app.logger.info(f"Compliance alert email sent for {nb} client(s)")
    else:
        app.logger.warning(
            "COMPLIANCE_ALERT_EMAIL not configured, skipping email alert"
        )

    lines = [f"📋 Résumé conformité workflow — {today.strftime('%d/%m/%Y')}"]
    lines.append(
        "⚠️ Estimation basée sur les salariés rattachés au logiciel, pas une attribution exacte par mission."
    )
    for client_name, client_id, violations in alerts_by_client:
        lines.append(f"\n🚨 {client_name} (client_id={client_id})")
        for v in violations:
            lines.append(f"  {v}")
    send_tchap_message("\n".join(lines))


@log_execution
def job_compute_software_compliance_snapshot(for_date=None):
    today = for_date or date.today()
    yesterday = today - timedelta(days=1)

    app.logger.info(f"Computing software compliance snapshot for {yesterday}")

    snapshots = _compute_and_store_snapshots(yesterday)

    alerts_by_client = []
    triggered_by_client = []
    for snapshot in snapshots:
        violations, triggered_fields = _get_violations(
            snapshot.client_id, today
        )
        if violations:
            alerts_by_client.append(
                (snapshot.client_name, snapshot.client_id, violations)
            )
            triggered_by_client.append((snapshot.client_id, triggered_fields))

    _send_consolidated_alert(alerts_by_client, today)

    for client_id, fields in triggered_by_client:
        for field in fields:
            state = SoftwareComplianceAlertState.query.filter_by(
                client_id=client_id, metric=field
            ).one_or_none()
            if state is None:
                db.session.add(
                    SoftwareComplianceAlertState(
                        client_id=client_id,
                        metric=field,
                        last_alerted_on=today,
                    )
                )
            else:
                state.last_alerted_on = today
    db.session.commit()

    app.logger.info(
        f"Software compliance snapshot done: "
        f"{len(snapshots)} clients computed, {len(alerts_by_client)} alerts sent"
    )
