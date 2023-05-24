from datetime import datetime

from app import db
from app.commands import _clean_vehicle
from app.models import Vehicle, Mission
from app.seed import CompanyFactory, UserFactory
from app.seed.factories import VehicleFactory, MissionFactory
from app.tests import BaseTest


class TestVehicleDeduplication(BaseTest):
    def vehicle_should_exist(self, vehicle_id):
        self.assertIsNotNone(Vehicle.query.get(vehicle_id))

    def vehicle_should_not_exist(self, vehicle_id):
        self.assertIsNone(Vehicle.query.get(vehicle_id))

    def setUp(self):
        super().setUp()
        self.company_1 = CompanyFactory.create()
        self.company_2 = CompanyFactory.create()
        self.user = UserFactory.create()

    def test_not_terminated_no_info(self):
        vehicle_1_1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-B-C 123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup2_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-b-C123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_2_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-B-D 123",
            submitter_id=self.user.id,
        ).id

        _clean_vehicle()
        db.session.expire_all()
        self.vehicle_should_not_exist(vehicle_1_1_id)
        self.vehicle_should_not_exist(vehicle_1_dup1_id)
        self.vehicle_should_exist(vehicle_1_dup2_id)
        self.vehicle_should_exist(vehicle_1_2_id)

    def test_keep_other_company(self):
        vehicle_1_1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id
        vehicle_2_1_id = VehicleFactory.create(
            company_id=self.company_2.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id

        _clean_vehicle()
        self.vehicle_should_exist(vehicle_1_1_id)
        self.vehicle_should_exist(vehicle_2_1_id)

    def test_terminated_no_info(self):
        vehicle_1_1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-B-C 123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup2_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-b-C123",
            submitter_id=self.user.id,
            terminated_at=datetime.now(),
        ).id
        _clean_vehicle()
        db.session.expire_all()
        self.vehicle_should_not_exist(vehicle_1_1_id)
        self.vehicle_should_exist(vehicle_1_dup1_id)
        self.vehicle_should_not_exist(vehicle_1_dup2_id)

    def test_with_alias(self):
        vehicle_1_1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-B-C 123",
            submitter_id=self.user.id,
            alias="ALIAS",
        ).id
        vehicle_1_dup2_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-b-C123",
            submitter_id=self.user.id,
        ).id
        _clean_vehicle()
        db.session.expire_all()
        self.vehicle_should_not_exist(vehicle_1_1_id)
        self.vehicle_should_exist(vehicle_1_dup1_id)
        self.vehicle_should_not_exist(vehicle_1_dup2_id)

    def test_with_kilometer(self):
        vehicle_1_1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-B-C 123",
            submitter_id=self.user.id,
            last_kilometer_reading=1234,
        ).id
        vehicle_1_dup2_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-b-C123",
            submitter_id=self.user.id,
        ).id
        _clean_vehicle()
        db.session.expire_all()
        self.vehicle_should_not_exist(vehicle_1_1_id)
        self.vehicle_should_exist(vehicle_1_dup1_id)
        self.vehicle_should_not_exist(vehicle_1_dup2_id)

    def test_mix_terminated_kilometer_kilometer(self):
        vehicle_1_1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="abc123",
            submitter_id=self.user.id,
        ).id
        vehicle_1_dup1_id = VehicleFactory.create(
            company_id=self.company_1.id,
            registration_number="A-B-C 123",
            submitter_id=self.user.id,
            last_kilometer_reading=1234,
        ).id
        mission = MissionFactory.create(
            company_id=self.company_1.id,
            vehicle_id=vehicle_1_1_id,
            submitter_id=self.user.id,
            reception_time=datetime.now(),
        )
        _clean_vehicle()
        db.session.expire_all()
        mission = Mission.query.get(mission.id)
        self.assertEqual(vehicle_1_dup1_id, mission.vehicle_id)

        self.vehicle_should_not_exist(vehicle_1_1_id)
        self.vehicle_should_exist(vehicle_1_dup1_id)
