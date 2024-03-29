import datetime

from app import db
from app.models import Employment, Team
from app.models.team_association_tables import (
    team_admin_user_association_table,
)
from app.seed import CompanyFactory, UserFactory, EmploymentFactory
from app.tests import BaseTest, test_post_graphql
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)

TEAM_A = "Equipe A"
TEAM_B = "Equipe B"


class TestTeam(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.admin_2 = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.employee = UserFactory.create(
            post__company=self.company, post__has_admin_rights=False
        )
        self.company_with_several_teams = CompanyFactory.create()
        self.admin_several_teams = UserFactory.create(
            post__company=self.company_with_several_teams,
            post__has_admin_rights=True,
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=self.admin_several_teams,
            has_admin_rights=True,
        )
        EmploymentFactory.create(
            company=self.company_with_several_teams,
            submitter=self.admin_several_teams,
            user=self.admin,
            has_admin_rights=True,
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
            "teams"
        ][0]["name"]
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
        admin_users = create_team_result["data"]["teams"]["createTeam"][
            "teams"
        ][0]["adminUsers"]
        self.assertEqual(1, len(admin_users))
        self.assertEqual(self.admin.id, admin_users[0]["id"])
        users = create_team_result["data"]["teams"]["createTeam"]["teams"][0][
            "users"
        ]
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
        known_addresses = create_team_result["data"]["teams"]["createTeam"][
            "teams"
        ][0]["knownAddresses"]
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
        vehicles = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["vehicles"]
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
        admin_users = create_team_result["data"]["teams"]["createTeam"][
            "teams"
        ][0]["adminUsers"]
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
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]
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
        users = update_team_result["data"]["teams"]["updateTeam"]["teams"][0][
            "users"
        ]
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
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]
        update_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.update_team,
            variables={"team_id": team_id, "name": new_team_name_input},
        )
        team_name_output = update_team_result["data"]["teams"]["updateTeam"][
            "teams"
        ][0]["name"]
        self.assertEqual(new_team_name_input, team_name_output)

    def test_remove_team(self):
        team_name_input = "Nom d'équipe"
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={"company_id": self.company.id, "name": team_name_input},
        )
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]
        delete_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.delete_team,
            variables={"team_id": team_id},
        )
        delete_team_output = delete_team_result["data"]["teams"]["deleteTeam"][
            "teams"
        ]
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

    def test_update_team_employment(self):
        team_ids = {}
        team_1 = TEAM_A
        team_2 = TEAM_B
        for team_name in [team_1, team_2]:
            team_result = make_authenticated_request(
                time=None,
                submitter_id=self.admin.id,
                query=ApiRequests.create_team,
                variables={
                    "company_id": self.company.id,
                    "name": team_name,
                },
            )
            created_team_id = team_result["data"]["teams"]["createTeam"][
                "teams"
            ][0]["id"]
            team_ids[team_name] = created_team_id

        ## employee starts with no team
        employment = Employment.query.filter(
            Employment.user_id == self.employee.id
        ).one_or_none()
        self.assertIsNone(employment.team_id)

        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.change_employee_team,
            variables={
                "company_id": employment.company_id,
                "user_id": self.employee.id,
                "team_id": team_ids[team_1],
            },
        )

        ## employee is now in Team A
        employment = Employment.query.filter(
            Employment.user_id == self.employee.id
        ).one_or_none()
        self.assertEqual(team_ids[team_1], employment.team_id)

        ## removing employee from any team
        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.change_employee_team,
            variables={
                "company_id": employment.company_id,
                "user_id": self.employee.id,
            },
        )

        ## employee is now in no team
        employment = Employment.query.filter(
            Employment.user_id == self.employee.id
        ).one_or_none()
        self.assertIsNone(employment.team_id)

    def test_update_employment_role_team_admin(self):
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": TEAM_A,
                "adminIds": [self.admin_2.id],
            },
        )
        data_result = create_team_result["data"]["teams"]["createTeam"][
            "teams"
        ][0]
        team_id = data_result["id"]
        self.assertEqual(len(data_result["adminUsers"]), 1)

        employment_admin_2 = Employment.query.filter(
            Employment.user_id == self.admin_2.id
        ).one_or_none()
        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.change_employee_role,
            variables={
                "employment_id": employment_admin_2.id,
                "has_admin_rights": False,
            },
        )

        team = Team.query.get(team_id)
        self.assertEqual(len(team.admin_users), 0)

    def test_remove_admin_rights_admin_should_still_be_team_admin_in_other_companies(
        self,
    ):
        team_name_a = TEAM_A
        team_name_b = TEAM_B
        for company in [self.company, self.company_with_several_teams]:
            for team_name in [team_name_a, team_name_b]:
                make_authenticated_request(
                    time=None,
                    submitter_id=self.admin_several_teams.id,
                    query=ApiRequests.create_team,
                    variables={
                        "company_id": company.id,
                        "name": team_name,
                        "adminIds": [self.admin_several_teams.id],
                    },
                )

        ## Our admin is admin of 4 teams (2 in company and 2 in company_with_several_teams
        self.assertEqual(
            db.session.query(team_admin_user_association_table).count(), 4
        )

        employment = Employment.query.filter(
            Employment.user_id == self.admin_several_teams.id,
            Employment.company_id == self.company_with_several_teams.id,
        ).one_or_none()

        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.change_employee_role,
            variables={
                "employment_id": employment.id,
                "has_admin_rights": False,
            },
        )
        self.assertEqual(
            db.session.query(team_admin_user_association_table).count(), 2
        )

        self.assertEqual(
            len(
                Team.query.filter(
                    Team.company == self.company, Team.name == team_name_a
                )
                .one_or_none()
                .admin_users
            ),
            1,
        )
        self.assertEqual(
            len(
                Team.query.filter(
                    Team.company == self.company_with_several_teams,
                    Team.name == team_name_a,
                )
                .one_or_none()
                .admin_users
            ),
            0,
        )

    def test_change_employee_team_should_update_all_employments(self):
        employee_with_history = UserFactory.create()
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": TEAM_A,
                "adminIds": [self.admin.id],
            },
        )
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]

        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=employee_with_history,
            has_admin_rights=False,
            start_date=datetime.date(2000, 1, 1),
            end_date=datetime.date(2002, 1, 1),
        )
        current_employment = EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=employee_with_history,
            has_admin_rights=False,
            start_date=datetime.date(2023, 1, 1),
        )
        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.change_employee_team,
            variables={
                "company_id": current_employment.company_id,
                "user_id": current_employment.user_id,
                "team_id": team_id,
            },
        )

        employments = Employment.query.filter(
            Employment.user_id == employee_with_history.id
        ).all()
        self.assertIsNone(
            Employment.query.filter(Employment.user_id == self.employee.id)
            .one_or_none()
            .team_id
        )
        self.assertEqual(len(employments), 2)
        self.assertEqual(employments[0].team_id, team_id)
        self.assertEqual(employments[1].team_id, team_id)

    def test_update_team_should_update_all_employments(self):
        employee_with_history = UserFactory.create()
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": TEAM_A,
                "adminIds": [self.admin.id],
            },
        )
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]

        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=employee_with_history,
            has_admin_rights=False,
            start_date=datetime.date(2000, 1, 1),
            end_date=datetime.date(2002, 1, 1),
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=employee_with_history,
            has_admin_rights=False,
            start_date=datetime.date(2023, 1, 1),
        )
        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.update_team,
            variables={
                "team_id": team_id,
                "name": TEAM_A,
                "userIds": [employee_with_history.id],
            },
        )

        employments = Employment.query.filter(
            Employment.user_id == employee_with_history.id
        ).all()
        self.assertIsNone(
            Employment.query.filter(Employment.user_id == self.employee.id)
            .one_or_none()
            .team_id
        )
        self.assertEqual(len(employments), 2)
        self.assertEqual(employments[0].team_id, team_id)
        self.assertEqual(employments[1].team_id, team_id)

    def test_invite_existing_user_should_update_all_employments(self):
        employee_with_history = UserFactory.create()
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": TEAM_A,
                "adminIds": [self.admin.id],
            },
        )
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]

        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=employee_with_history,
            has_admin_rights=False,
            start_date=datetime.date(2000, 1, 1),
            end_date=datetime.date(2002, 1, 1),
        )

        test_post_graphql(
            ApiRequests.invite,
            mock_authentication_with_user=self.admin,
            variables=dict(
                userId=employee_with_history.id,
                companyId=self.company.id,
                teamId=team_id,
            ),
        )

        employments = Employment.query.filter(
            Employment.user_id == employee_with_history.id
        ).all()
        self.assertIsNone(
            Employment.query.filter(Employment.user_id == self.employee.id)
            .one_or_none()
            .team_id
        )
        self.assertEqual(len(employments), 2)
        self.assertEqual(employments[0].team_id, team_id)
        self.assertEqual(employments[1].team_id, team_id)

    def test_redeem_invitation_should_apply_team_to_previous_employments(self):
        employee_with_history = UserFactory.create()
        create_team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company.id,
                "name": TEAM_A,
                "adminIds": [self.admin.id],
            },
        )
        team_id = create_team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=employee_with_history,
            has_admin_rights=False,
            start_date=datetime.date(2000, 1, 1),
            end_date=datetime.date(2002, 1, 1),
        )

        test_post_graphql(
            ApiRequests.invite,
            mock_authentication_with_user=self.admin,
            variables=dict(
                mail="email@test.com",
                companyId=self.company.id,
                teamId=team_id,
            ),
        )
        invite_token = (
            Employment.query.filter(Employment.user_id == None)
            .one_or_none()
            .invite_token
        )

        make_authenticated_request(
            time=datetime.datetime.now(),
            submitter_id=employee_with_history.id,
            query=ApiRequests.redeem_invite,
            variables=dict(
                token=invite_token,
            ),
            unexposed_query=True,
        )

        employments = Employment.query.filter(
            Employment.user_id == employee_with_history.id
        ).all()
        self.assertIsNone(
            Employment.query.filter(Employment.user_id == self.employee.id)
            .one_or_none()
            .team_id
        )
        self.assertEqual(len(employments), 2)
        self.assertEqual(employments[0].team_id, team_id)
        self.assertEqual(employments[1].team_id, team_id)

    def test_update_team_wrong_company_has_no_effect(self):

        # creating a team in another company
        team_result = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.create_team,
            variables={
                "company_id": self.company_with_several_teams.id,
                "name": TEAM_A,
            },
        )
        created_team_id = team_result["data"]["teams"]["createTeam"]["teams"][
            0
        ]["id"]

        ## employee starts with no team
        employment = Employment.query.filter(
            Employment.user_id == self.employee.id
        ).one_or_none()
        self.assertIsNone(employment.team_id)

        make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.change_employee_team,
            variables={
                "company_id": employment.company_id,
                "user_id": self.employee.id,
                "team_id": created_team_id,
            },
        )

        ## employee is now in Team A
        employment = Employment.query.filter(
            Employment.user_id == self.employee.id
        ).one_or_none()
        self.assertIsNone(employment.team_id)
