from app import db
from typing import List, Set
from datetime import datetime
from app.services.anonymization.base import BaseAnonymizer
from app.models import (
    User,
    Mission,
    Employment,
    ControllerControl,
    RegulatoryAlert,
    RegulationComputation,
    UserAgreement,
)
from app.models.team_association_tables import (
    team_admin_user_association_table,
)
import logging

logger = logging.getLogger(__name__)


# TODO:
# 1. Créer les modèles anonymisés:
#    - TeamAnonymized
#    - TeamAdminUserAnonymized
#    - TeamKnownAddressAnonymized
# 2. Pour team_vehicle: pas de modèle anonymisé, suppression directe
# 3. Ajouter dans base.py une fonction anonymize_team_and_dependencies qui gère:
#    - L'anonymisation de team
#    - L'anonymisation des relations team_admin_user et team_known_address
#    - La suppression des relations team_vehicle


class UserAnonymizer(BaseAnonymizer):
    def anonymize_user_data(
        self,
        full_anonymization_users: Set[int],
        partial_anonymization_users: Set[int],
        test_mode: bool = False,
    ):
        transaction = db.session.begin_nested()
        try:
            if full_anonymization_users:
                logger.info(
                    f"Processing {len(full_anonymization_users)} users for full anonymization"
                )

                # Récupération des IDs
                user_mission_ids = self.find_user_missions(
                    full_anonymization_users
                )
                user_employment_ids = self.find_user_employments(
                    full_anonymization_users
                )
                user_control_ids = self.find_user_controls(
                    full_anonymization_users
                )
                user_regulatory_alert_ids = self.find_user_regulatory_alerts(
                    full_anonymization_users
                )
                user_regulation_computation_ids = (
                    self.find_user_regulation_computations(
                        full_anonymization_users
                    )
                )
                user_agreement_ids = self.find_user_agreements(
                    full_anonymization_users
                )
                team_ids = self.find_team_admins_by_users(
                    full_anonymization_users
                )
                team_ids.update(self.find_user_teams(full_anonymization_users))

                # Anonymisation des données
                if user_mission_ids:
                    self.anonymize_mission_and_dependencies(
                        list(user_mission_ids)
                    )
                if user_employment_ids:
                    self.anonymize_employment_and_dependencies(
                        list(user_employment_ids)
                    )
                if user_control_ids:
                    self.anonymize_controller_controls(list(user_control_ids))
                if user_regulatory_alert_ids:
                    self.anonymize_regulatory_alerts(
                        list(user_regulatory_alert_ids)
                    )
                if user_regulation_computation_ids:
                    self.anonymize_regulation_computations(
                        list(user_regulation_computation_ids)
                    )
                if user_agreement_ids:
                    self.anonymize_user_agreements(list(user_agreement_ids))
                if team_ids:
                    self.anonymize_team_and_dependencies(list(team_ids))

                self.anonymize_users(list(full_anonymization_users))

            if not any(
                [full_anonymization_users, partial_anonymization_users]
            ):
                logger.info("No user data to anonymize")
                transaction.rollback()
                return

            if test_mode:
                logger.info("Test mode: rolling back changes")
                transaction.rollback()
                db.session.rollback()
            else:
                logger.info("Committing user data changes...")
                transaction.commit()
                db.session.commit()

        except Exception as e:
            logger.error(f"Error processing user data: {e}")
            transaction.rollback()
            db.session.rollback()
            raise

    def find_user_missions(self, user_ids: Set[int]) -> Set[int]:
        missions = Mission.query.filter(
            Mission.submitter_id.in_(user_ids)
        ).all()

        if not missions:
            logger.info("No user missions found")
            return set()

        mission_ids = {m.id for m in missions}
        logger.info(f"Found {len(mission_ids)} user missions to anonymize")
        return mission_ids

    def find_user_employments(self, user_ids: Set[int]) -> Set[int]:
        employments = Employment.query.filter(
            Employment.user_id.in_(user_ids)
        ).all()

        if not employments:
            logger.info("No user employments found")
            return set()

        employment_ids = {e.id for e in employments}
        logger.info(
            f"Found {len(employment_ids)} user employments to anonymize"
        )
        return employment_ids

    def find_user_controls(self, user_ids: Set[int]) -> Set[int]:
        controls = ControllerControl.query.filter(
            ControllerControl.user_id.in_(user_ids)
        ).all()

        if not controls:
            logger.info("No user controls found")
            return set()

        control_ids = {c.id for c in controls}
        logger.info(
            f"Found {len(control_ids)} controller controls to anonymize"
        )
        return control_ids

    def find_user_regulatory_alerts(self, user_ids: Set[int]) -> Set[int]:
        alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_(user_ids)
        ).all()

        if not alerts:
            logger.info("No regulatory alerts found")
            return set()

        alert_ids = {a.id for a in alerts}
        logger.info(f"Found {len(alert_ids)} regulatory alerts to anonymize")
        return alert_ids

    def find_user_regulation_computations(
        self, user_ids: Set[int]
    ) -> Set[int]:
        computations = RegulationComputation.query.filter(
            RegulationComputation.user_id.in_(user_ids)
        ).all()

        if not computations:
            logger.info("No regulation computations found")
            return set()

        computation_ids = {c.id for c in computations}
        logger.info(
            f"Found {len(computation_ids)} regulation computations to anonymize"
        )
        return computation_ids

    def find_team_admins_by_users(self, user_ids: Set[int]) -> Set[int]:
        result = (
            db.session.query(team_admin_user_association_table)
            .filter(team_admin_user_association_table.c.user_id.in_(user_ids))
            .all()
        )

        if not result:
            logger.info("No team admin relations found")
            return set()

        team_ids = {r.team_id for r in result}
        logger.info(f"Found {len(team_ids)} team admin relations to anonymize")
        return team_ids

    def find_user_agreements(self, user_ids: Set[int]) -> Set[int]:
        agreements = UserAgreement.query.filter(
            UserAgreement.user_id.in_(user_ids)
        ).all()

        if not agreements:
            logger.info("No user agreements found")
            return set()

        agreement_ids = {a.id for a in agreements}
        logger.info(f"Found {len(agreement_ids)} user agreements to anonymize")
        return agreement_ids
