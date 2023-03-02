from app.seed import CompanyFactory, UserFactory
from app.tests import BaseTest, test_post_graphql_unexposed
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestTeam(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.employee = UserFactory.create(
            post__company=self.company, post__has_admin_rights=False
        )

    def test_team_creation_only_name(self):
        team_name_input = "Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={"company_id": self.company.id, "name": team_name_input},
        )
        team_name_output = create_team_result["data"]["teams"]["createTeam"][
            0
        ]["name"]
        self.assertEqual(team_name_input, team_name_output)

    def test_team_creation_with_user_and_admin(self):
        team_name_input = "Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": team_name_input,
                "userIds": [self.employee.id],
                "adminIds": [self.admin.id],
            },
        )
        admin_users = create_team_result["data"]["teams"]["createTeam"][0][
            "adminUsers"
        ]
        self.assertEqual(1, len(admin_users))
        self.assertEqual(self.admin.id, admin_users[0]["id"])
        users = create_team_result["data"]["teams"]["createTeam"][0]["users"]
        self.assertEqual(1, len(users))
        self.assertEqual(self.employee.id, users[0]["id"])

    def test_team_creation_with_address(self):
        team_name_input = "Nom d'équipe"
        create_address_response = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_address,
            variables={
                "companyId": self.company.id,
                "manualAddress": "1 rue Test",
            },
            unexposed_query=True,
        )
        address_id = create_address_response["data"]["locations"][
            "createKnownAddress"
        ]["id"]
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": team_name_input,
                "knownAddressIds": [address_id],
            },
        )
        known_addresses = create_team_result["data"]["teams"]["createTeam"][0][
            "knownAddresses"
        ]
        self.assertEqual(1, len(known_addresses))
        self.assertEqual(address_id, known_addresses[0]["id"])

    def test_team_creation_with_vehicle(self):
        team_name_input = "Nom d'équipe"
        create_vehicle_response = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_vehicle,
            variables={
                "companyId": self.company.id,
                "registrationNumber": "227 JEL 75",
            },
            unexposed_query=True,
        )
        vehicle_id = create_vehicle_response["data"]["vehicles"][
            "createVehicle"
        ]["id"]
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": team_name_input,
                "vehicleIds": [vehicle_id],
            },
        )
        vehicles = create_team_result["data"]["teams"]["createTeam"][0][
            "vehicles"
        ]
        self.assertEqual(1, len(vehicles))
        self.assertEqual(vehicle_id, vehicles[0]["id"])

    def test_team_user_can_not_be_admin(self):
        team_name_input = "Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": team_name_input,
                "adminIds": [self.employee.id],
            },
        )
        admin_users = create_team_result["data"]["teams"]["createTeam"][0][
            "adminUsers"
        ]
        self.assertEqual(0, len(admin_users))

    def test_team_remove_one_user(self):
        team_name_input = "Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": team_name_input,
                "userIds": [self.employee.id, self.admin.id],
            },
        )
        team_id = create_team_result["data"]["teams"]["createTeam"][0]["id"]
        update_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.update_team,
            variables={
                "team_id": team_id,
                "name": team_name_input,
                "userIds": [self.employee.id],
            },
        )
        users = update_team_result["data"]["teams"]["updateTeam"][0]["users"]
        self.assertEqual(1, len(users))
        self.assertEqual(self.employee.id, users[0]["id"])

    def test_team_update_name(self):
        team_name_input = "Nom d'équipe"
        new_team_name_input = "Nouveau Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={"company_id": self.company.id, "name": team_name_input},
        )
        team_id = create_team_result["data"]["teams"]["createTeam"][0]["id"]
        update_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.update_team,
            variables={"team_id": team_id, "name": new_team_name_input},
        )
        team_name_output = update_team_result["data"]["teams"]["updateTeam"][
            0
        ]["name"]
        self.assertEqual(new_team_name_input, team_name_output)

    def test_remove_team(self):
        team_name_input = "Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={"company_id": self.company.id, "name": team_name_input},
        )
        team_id = create_team_result["data"]["teams"]["createTeam"][0]["id"]
        delete_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.delete_team,
            variables={"team_id": team_id},
        )
        delete_team_output = delete_team_result["data"]["teams"]["deleteTeam"]
        self.assertEqual(0, len(delete_team_output))

    def test_team_update_wrong_company(self):
        response = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.update_team,
            variables={"team_id": 1234, "name": "nom d'équipe"},
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "AUTHORIZATION_ERROR"
        )
