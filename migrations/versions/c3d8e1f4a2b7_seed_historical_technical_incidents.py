"""seed historical technical incidents

Revision ID: c3d8e1f4a2b7
Revises: b1e7c9a2f4d3
Create Date: 2026-09-14 09:00:00.000000

"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d8e1f4a2b7"
down_revision = "b1e7c9a2f4d3"
branch_labels = None
depends_on = None

# Historique repris du registre GitBook. Figé dans la migration pour rester
# immuable (horaires approximatifs quand le registre ne donne que le jour).
# Times are naive UTC, consistent with DateTimeStoredAsUTC.
INCIDENTS = [
    {
        "technical_type": "slowdown_timeout",
        "start_time": "2026-07-15T11:00:00",
        "end_time": "2026-07-15T16:00:00",
        "description": (
            "504 Gateway Timeout global en production. Deux causes cumulées "
            "ont saturé les workers web et la base de données : l'endpoint "
            "/next-webinars appelait l'API Livestorm en synchrone dans un "
            "worker web (une lenteur du tiers bloquait le worker), et la "
            "requête SQL dashboard_summary (_count_pending_validations) "
            "exécutait un EXISTS décorrélé que SQLAlchemy transformait en JOIN "
            "sur toute la table (jusqu'à 70 min sur une entreprise de 161 000 "
            "missions). Services impactés : interface gestionnaire (dashboard, "
            "tableau des missions), interface salarié (indirectement via "
            "saturation du back-end), requêtes GraphQL passant par les workers "
            "web. Résolu (PR #734, commit c02d3022) par .correlate(Mission, "
            "Activity) sur l'EXISTS, un JOIN borné sur les mission_id récents, "
            "et la sortie de l'appel Livestorm du pool web (cron "
            "refresh_webinars_cache via Redis)."
        ),
    },
    {
        "technical_type": "dns_switch",
        "start_time": "2025-10-23T19:00:00",
        "end_time": "2025-10-24T11:00:00",
        "description": (
            "Bascule DNS sur OVH pour changer de prestataire de cybersécurité "
            "(Baleen -> OGO). Les requêtes en IPv6 ont été bloquées (non "
            "acceptées par l'hébergeur Scalingo mais paramétrées chez OGO), et "
            "certaines requêtes remontaient une erreur 508 à cause d'une "
            "réécriture des appels API créant une alerte de boucle chez OGO. "
            "Services impactés : interface Mobilic, utilisateurs en IPv6 "
            "(actions impossibles). Résolu : OGO limité à l'IPv4 + ajout des "
            "IP publiques Scalingo en exception, restauration de la "
            "configuration DNS initiale vers Baleen, suppression du header Ogo "
            "côté nginx."
        ),
    },
    {
        "technical_type": "auth_outage",
        "start_time": "2025-06-13T17:06:00",
        "end_time": "2025-06-13T21:00:00",
        "description": (
            "Fournisseurs d'identités RIE indisponibles suite à un incident "
            "hébergeur : connexion via ProConnect impossible à partir du "
            "13/06/2025 17h06. Rétablissement dans la soirée après résolution "
            "de l'incident hébergeur."
        ),
    },
    {
        "technical_type": "auth_outage",
        "start_time": "2025-03-03T08:00:00",
        "end_time": "2025-03-04T20:00:00",
        "description": (
            "Panne majeure du système de refroidissement du centre serveur du "
            "ministère de la transition écologique (MTE). Tous les services "
            ".developpement-durable.gouv.fr impactés (BNUM, webconf, Grist, "
            "Cerbère), et donc les services accessibles via ProConnect "
            "(dépendance à Cerbère) -> connexion à Mobilic impossible. "
            "Contournement : utilisation d'adresses email betagouv pour éviter "
            "Cerbère. Rétablissement partiel le 04/03/2025 avec "
            "coupures/ralentissements résiduels. Horaires approximatifs (le "
            "registre ne précise que les jours)."
        ),
    },
    {
        "technical_type": "third_party_outage",
        "start_time": "2025-01-20T09:00:00",
        "end_time": "2025-02-10T18:00:00",
        "description": (
            "Problème d'intégration du logiciel tiers Timesheet Mobile (TSM) : "
            "les missions étaient créées mais les autres informations "
            "(activités, fin, validation) n'étaient pas correctement remontées "
            "(OVERLAPPING_MISSIONS, nombreuses activités sans date de fin, "
            "validations vides). La disponibilité des données a été compromise "
            "(intégrité non affectée). Résolu par collaboration Mobilic/TSM : "
            "reprise des données historiques du 24/09/2024 au 31/01/2025. "
            "Horaires approximatifs (le registre ne précise que les jours)."
        ),
    },
]


def _parse(value):
    return datetime.fromisoformat(value) if value else None


def upgrade():
    bind = op.get_bind()
    # Natural key (start_time, technical_type) to stay idempotent on replay.
    existing = {
        (row[0], row[1])
        for row in bind.execute(
            sa.text(
                "SELECT start_time, technical_type FROM technical_incident"
            )
        )
    }

    insert = sa.text(
        "INSERT INTO technical_incident "
        "(creation_time, technical_type, start_time, end_time, description) "
        "VALUES (:creation_time, :technical_type, :start_time, :end_time, "
        ":description)"
    )
    now = datetime.utcnow()
    for data in INCIDENTS:
        start_time = _parse(data["start_time"])
        if (start_time, data["technical_type"]) in existing:
            continue
        bind.execute(
            insert,
            creation_time=now,
            technical_type=data["technical_type"],
            start_time=start_time,
            end_time=_parse(data["end_time"]),
            description=data["description"],
        )


def downgrade():
    bind = op.get_bind()
    delete = sa.text(
        "DELETE FROM technical_incident "
        "WHERE start_time = :start_time AND technical_type = :technical_type"
    )
    for data in INCIDENTS:
        bind.execute(
            delete,
            start_time=_parse(data["start_time"]),
            technical_type=data["technical_type"],
        )
