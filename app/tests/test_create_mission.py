from datetime import datetime

from app import db
from app.models.vehicle import Vehicle
from app.seed import UserFactory, CompanyFactory
from app.seed.factories import TeamFactory
from app.tests import BaseTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)


def _get_vehicle(company_id, registration_number):
    return db.session.execute(
        """
        SELECT v.id FROM vehicle v 
        WHERE v.company_id = :company_id
        AND v.registration_number = :registration_number
        """,
        dict(
            company_id=company_id,
            registration_number=registration_number,
        ),
    ).fetchone()


def _get_team_for_vehicle(vehicle_id):
    return db.session.execute(
        """
        SELECT tv.team_id FROM team_vehicle tv
        WHERE tv.vehicle_id = :vehicle_id
        """,
        dict(vehicle_id=vehicle_id),
    ).fetchone()


def _add_vehicle_to_team(company_id, registration_number, team_id):
    db.session.execute(
        """
        INSERT INTO team_vehicle (team_id, vehicle_id)
        SELECT :team_id, v.id FROM vehicle v
        WHERE v.company_id = :company_id
        AND v.registration_number = :registration_number
        """,
        dict(
            team_id=team_id,
            company_id=company_id,
            registration_number=registration_number,
        ),
    )


class TestCreateMission(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.team = TeamFactory.create(company=self.company)
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.noteam_employee = UserFactory.create(post__company=self.company)
        self.team_employee = UserFactory.create(
            post__company=self.company,
            post__team=self.team,
        )

    def test_create_mission_vehicle_no_team(self):
        # Given new vehicle
        registration_number = "ABC-123-XYZ"

        # When creating mission
        make_authenticated_request(
            time=datetime(2023, 1, 1),
            submitter_id=self.noteam_employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": self.company.id,
                "vehicle_registration_number": registration_number,
            },
        )

        # Then vehicle is linked to company
        vehicle = _get_vehicle(self.company.id, registration_number)
        self.assertIsNotNone(vehicle)

        # Then vehicle is not linked to a team
        team_id = _get_team_for_vehicle(vehicle.id)
        self.assertIsNone(team_id)

    def test_create_mission_vehicle_with_team(self):
        # Given no team vehicle
        registration_number = "XYZ-999-XYZ"

        # When creating mission with new vehicle
        make_authenticated_request(
            time=datetime(2023, 1, 1),
            submitter_id=self.team_employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": self.company.id,
                "vehicle_registration_number": registration_number,
            },
        )

        # Then vehicle is linked to company
        vehicle = _get_vehicle(self.company.id, registration_number)
        self.assertIsNotNone(vehicle)

        # Then vehicle is not linked to a team
        team_id = _get_team_for_vehicle(vehicle.id)
        self.assertIsNone(team_id)

        # ----
        # Given there is already one team vehicle
        _add_vehicle_to_team(
            self.company.id, registration_number, self.team.id
        )
        registration_number = "AAA-111-ZZZ"

        # When creating mission with new vehicle
        make_authenticated_request(
            time=datetime(2023, 1, 1),
            submitter_id=self.team_employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": self.company.id,
                "vehicle_registration_number": registration_number,
            },
        )

        # Then vehicle is linked to company
        vehicle = _get_vehicle(self.company.id, registration_number)
        self.assertIsNotNone(vehicle.id)

        # Then vehicle is linked to a team
        team_id = _get_team_for_vehicle(vehicle.id)
        self.assertIsNotNone(team_id)

        # ----
        # Given existing vehicle in company
        registration_number = "ABC-000-CBA"
        existing_vehicle = Vehicle(
            registration_number=registration_number,
            submitter=self.admin,
            company_id=self.company.id,
        )
        db.session.add(existing_vehicle)

        # When creating mission with vehicle
        make_authenticated_request(
            time=datetime(2023, 1, 1),
            submitter_id=self.team_employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": self.company.id,
                "vehicle_registration_number": registration_number,
            },
        )

        # Then vehicle is linked to a team
        team_id = _get_team_for_vehicle(existing_vehicle.id)
        self.assertIsNotNone(team_id)

        # ----
        # Given vehicle already linked to the team

        # When creating mission with vehicle
        make_authenticated_request(
            time=datetime(2023, 1, 1),
            submitter_id=self.team_employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": self.company.id,
                "vehicle_registration_number": registration_number,
            },
        )

        # Then vehicle is still linked to a team
        team_id = _get_team_for_vehicle(existing_vehicle.id)
        self.assertIsNotNone(team_id)
