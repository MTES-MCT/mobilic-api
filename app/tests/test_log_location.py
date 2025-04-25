from datetime import datetime

from app.models.activity import ActivityType
from app.models.address import Address
from app.seed import UserFactory
from app.seed.factories import CompanyFactory, VehicleFactory
from app.tests import BaseTest
from app.tests.helpers import ApiRequests, make_authenticated_request


class TestLogLocation(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.employee = UserFactory.create(
            first_name="Employ", last_name="Yi", post__company=self.company
        )
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.vehicle = VehicleFactory.create(
            company_id=self.company.id,
            registration_number="CLIO_2001_ID",
            alias="Titine, la terreur des départementales",
        )
        self.geo_api_data = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [2.412745, 47.107928],
            },
            "properties": {
                "label": "Avenue du Général de Gaulle 18000 Bourges",
                "score": 0.8891745454545453,
                "id": "18033_2461",
                "name": "Avenue du Général de Gaulle",
                "postcode": "18000",
                "citycode": "18033",
                "x": 655466.12,
                "y": 6667684.16,
                "city": "Bourges",
                "context": "18, Cher, Centre-Val de Loire",
                "type": "street",
                "importance": 0.78092,
            },
        }

    def begin_mission(self, time, vehicle=None):
        variables = {
            "company_id": self.company.id,
        }
        if vehicle:
            variables["vehicle_id"] = vehicle.id

        create_mission_response = make_authenticated_request(
            time=time,
            submitter_id=self.employee.id,
            query=ApiRequests.create_mission,
            variables=variables,
        )
        mission_id = create_mission_response["data"]["activities"][
            "createMission"
        ]["id"]
        make_authenticated_request(
            time=time,
            submitter_id=self.employee.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=time,
                mission_id=mission_id,
                type=ActivityType.WORK,
                user_id=self.employee.id,
                switch=True,
            ),
        )
        return mission_id

    def test_log_location_should_not_create_twice_same_address(self):
        mission_id = self.begin_mission(datetime(2020, 2, 7, 6))
        geo_api_data = self.geo_api_data

        make_authenticated_request(
            time=datetime(2020, 2, 7, 7),
            submitter_id=self.employee.id,
            query=ApiRequests.log_location,
            variables=dict(
                mission_id=mission_id,
                type="mission_start_location",
                geoApiData=geo_api_data,
            ),
        )
        self.assertEqual(
            Address.query.filter(
                Address.name == "Avenue du Général de Gaulle",
                Address.postal_code == "18000",
                Address.city == "Bourges",
            ).count(),
            1,
        )

        make_authenticated_request(
            time=datetime(2020, 2, 7, 7),
            submitter_id=self.employee.id,
            query=ApiRequests.log_location,
            variables=dict(
                mission_id=mission_id,
                type="mission_end_location",
                geoApiData=geo_api_data,
            ),
        )
        self.assertEqual(
            Address.query.filter(
                Address.name == "Avenue du Général de Gaulle",
                Address.postal_code == "18000",
                Address.city == "Bourges",
            ).count(),
            1,
        )

    def test_log_location_with_vehicle_start_location(self):
        mission_id = self.begin_mission(datetime(2020, 2, 7, 6), self.vehicle)
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.employee.id,
            query=ApiRequests.log_location,
            variables=dict(
                mission_id=mission_id,
                type="mission_start_location",
                geoApiData=self.geo_api_data,
                kilometerReading=100,
            ),
        )
        self.assertNotIn("errors", response)

    def test_log_location_with_vehicle_end_location(self):
        mission_id = self.begin_mission(datetime(2020, 2, 7, 6), self.vehicle)
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.employee.id,
            query=ApiRequests.log_location,
            variables=dict(
                mission_id=mission_id,
                type="mission_end_location",
                geoApiData=self.geo_api_data,
                kilometerReading=150,
            ),
        )
        self.assertNotIn("errors", response)

    def test_log_location_without_vehicle_start_location(self):
        mission_id = self.begin_mission(datetime(2020, 2, 7, 6))
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.employee.id,
            query=ApiRequests.log_location,
            variables=dict(
                mission_id=mission_id,
                type="mission_start_location",
                geoApiData=self.geo_api_data,
                kilometerReading=100,
            ),
        )
        self.assertIn("errors", response)

    def test_log_location_without_vehicle_end_location(self):
        mission_id = self.begin_mission(datetime(2020, 2, 7, 6))
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.employee.id,
            query=ApiRequests.log_location,
            variables=dict(
                mission_id=mission_id,
                type="mission_end_location",
                geoApiData=self.geo_api_data,
                kilometerReading=150,
            ),
        )
        self.assertIn("errors", response)
