from datetime import datetime

from argon2 import PasswordHasher
from freezegun import freeze_time

from app import db
from app.helpers.oauth.models import OAuth2Client, ThirdPartyClientEmployment
from app.helpers.time import to_timestamp
from app.models import Employment
from app.models.activity import ActivityType
from app.models.employment import EmploymentRequestValidationStatus
from app.seed.factories import CompanyFactory, ThirdPartyApiKeyFactory
from app.seed.helpers import get_time
from app.tests import (
    BaseTest,
    test_post_graphql,
    test_post_graphql_unexposed,
    test_post_rest,
)
from app.tests.helpers import (
    ApiRequests,
    make_authenticated_request,
    make_protected_request,
)


def _software_registration(self, usual_name, siren):
    software_registration_response = make_protected_request(
        query=ApiRequests.software_registration,
        variables=dict(
            client_id=self.client_id, usual_name=usual_name, siren=siren
        ),
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-API-KEY": "mobilic_live_" + self.api_key,
        },
    )
    company_id = software_registration_response["data"]["company"][
        "softwareRegistration"
    ]["id"]
    self.assertIsNotNone(company_id)
    return company_id


def _sync_employments(self):
    sync_employment_response = make_protected_request(
        query=ApiRequests.sync_employment,
        variables=dict(
            company_id=self.company_id,
            employees=[
                {
                    "firstName": "Admin_test",
                    "lastName": "Admin_test",
                    "email": "email-admin@example.com",
                    "hasAdminRights": True,
                },
                {
                    "firstName": "Employee_test",
                    "lastName": "Employee_test",
                    "email": "email-employee@example.com",
                },
                {
                    "firstName": "Admin_dismissed",
                    "lastName": "Admin_dismissed",
                    "email": "email-admin-dismissed@example.com",
                    "hasAdminRights": True,
                },
            ],
        ),
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-API-KEY": "mobilic_live_" + self.api_key,
        },
    )
    employment_ids = sync_employment_response["data"]["company"][
        "syncEmployment"
    ]
    self.assertEqual(len(employment_ids), 3)
    self.employment_admin_id = employment_ids[0]["id"]
    self.employment_employee_id = employment_ids[1]["id"]
    self.employment_admin_id_2 = employment_ids[2]["id"]


def _get_user_id(self, employment_id):
    get_employment_token_response = make_protected_request(
        query=ApiRequests.get_employment_token,
        variables=dict(employment_id=employment_id, client_id=self.client_id),
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-API-KEY": "mobilic_live_" + self.api_key,
        },
    )
    user_id = get_employment_token_response["data"]["employmentToken"][
        "employment"
    ]["user"]["id"]
    self.assertIsNotNone(user_id)
    return user_id


def _active_employment(self, employment_id):
    third_party_client_employment = ThirdPartyClientEmployment.query.filter(
        ThirdPartyClientEmployment.employment_id == employment_id,
        ThirdPartyClientEmployment.client_id == self.client_id,
    ).one_or_none()
    self.assertIsNotNone(third_party_client_employment)
    invitation_token = third_party_client_employment.invitation_token
    self.assertIsNotNone(invitation_token)

    generate_employment_token_response = test_post_graphql_unexposed(
        query=ApiRequests.generate_employment_token,
        variables=dict(
            clientId=self.client_id,
            employmentId=employment_id,
            invitationToken=invitation_token,
        ),
    )
    self.assertEqual(generate_employment_token_response.status_code, 200)
    self.assertTrue(
        generate_employment_token_response.json["data"][
            "generateEmploymentToken"
        ]["success"]
    )


def _get_access_token(self, employment_id):
    _active_employment(self, employment_id)

    get_employment_token_response = make_protected_request(
        query=ApiRequests.get_employment_token,
        variables=dict(employment_id=employment_id, client_id=self.client_id),
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-API-KEY": "mobilic_live_" + self.api_key,
        },
    )
    access_token = get_employment_token_response["data"]["employmentToken"][
        "accessToken"
    ]
    self.assertIsNotNone(access_token)
    return access_token


def _dismiss_employment_token(self, employment_id, user_id):
    make_authenticated_request(
        time=datetime.now(),
        submitter_id=user_id,
        query=ApiRequests.dismiss_employment_token,
        variables=dict(
            clientId=self.client_id,
            employmentId=employment_id,
        ),
        unexposed_query=True,
    )


def _create_vehicle_success(self):
    create_vehicle_response = test_post_graphql_unexposed(
        query=ApiRequests.create_vehicle,
        variables={
            "companyId": self.company_id,
            "registrationNumber": "ABD123DEF",
            "alias": "My Little Truck",
        },
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(create_vehicle_response.status_code, 200)
    vehicle_id = create_vehicle_response.json["data"]["vehicles"][
        "createVehicle"
    ]["id"]
    self.assertIsNotNone(vehicle_id)
    return vehicle_id


def _create_address_success(self):
    create_address_response = test_post_graphql_unexposed(
        query=ApiRequests.create_address,
        variables={
            "companyId": self.company_id,
            "manualAddress": "1 rue du Pôle Nord",
            "alias": "Père Noël",
        },
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(create_address_response.status_code, 200)
    address_id = create_address_response.json["data"]["locations"][
        "createKnownAddress"
    ]["id"]
    self.assertIsNotNone(address_id)
    return address_id


def _create_employment_success(self):
    create_employment_response = test_post_graphql(
        query=ApiRequests.invite,
        variables={
            "companyId": self.company_id,
            "hasAdminRights": False,
            "mail": "employee-invited@test.com",
        },
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(create_employment_response.status_code, 200)
    employment_id = create_employment_response.json["data"]["employments"][
        "createEmployment"
    ]["id"]
    self.assertIsNotNone(employment_id)
    return employment_id


def _create_mission(company_id, headers):
    return test_post_graphql(
        query=ApiRequests.create_mission,
        variables={"companyId": company_id},
        headers=headers,
    )


def _create_mission_success(self):
    create_mission_response = _create_mission(
        self.company_id,
        {
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(create_mission_response.status_code, 200)
    mission_id = create_mission_response.json["data"]["activities"][
        "createMission"
    ]["id"]
    self.assertIsNotNone(mission_id)
    return mission_id


def _log_activity(mission_id, user_id, headers):
    return test_post_graphql(
        query=ApiRequests.log_activity,
        variables={
            "startTime": to_timestamp(datetime.now()),
            "missionId": mission_id,
            "type": ActivityType.WORK,
            "userId": user_id,
            "switch": True,
        },
        headers=headers,
    )


def _log_activity_success(self, mission_id, user_id):
    log_activity_response = _log_activity(
        mission_id,
        user_id,
        {
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(log_activity_response.status_code, 200)
    activity_id = log_activity_response.json["data"]["activities"][
        "logActivity"
    ]["id"]
    user_id_response = log_activity_response.json["data"]["activities"][
        "logActivity"
    ]["userId"]
    self.assertIsNotNone(activity_id)
    self.assertEqual(user_id_response, user_id)
    return activity_id


def _log_comment_success(self, mission_id):
    log_comment_response = test_post_graphql(
        query=ApiRequests.log_comment,
        variables={"missionId": mission_id, "text": "Test comment"},
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(log_comment_response.status_code, 200)
    comment_id = log_comment_response.json["data"]["activities"]["logComment"][
        "id"
    ]
    self.assertIsNotNone(comment_id)
    return comment_id


def _end_mission_success(self, mission_id, user_id):
    end_mission_response = test_post_graphql(
        query=ApiRequests.end_mission,
        variables={
            "missionId": mission_id,
            "endTime": to_timestamp(datetime.now()),
            "userId": user_id,
        },
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(end_mission_response.status_code, 200)
    if "errors" in end_mission_response.json:
        self.fail(
            f"End mission returned an error: {end_mission_response.json}"
        )


def _log_expenditure_success(self):
    with freeze_time(get_time(how_many_days_ago=0, hour=1)):
        mission_id = _create_mission_success(self)
        _log_activity_success(self, mission_id, self.user_employee_id)

    _end_mission_success(self, mission_id, self.user_employee_id)
    log_expenditure_response = test_post_graphql(
        query=ApiRequests.log_expenditure,
        variables={
            "type": "snack",
            "missionId": mission_id,
            "spendingDate": datetime.now().strftime("%Y-%m-%d"),
            "userId": self.user_employee_id,
        },
        headers={
            "X-CLIENT-ID": self.client_id,
            "X-EMPLOYMENT-TOKEN": self.access_token,
        },
    )
    self.assertEqual(log_expenditure_response.status_code, 200)
    expenditure_id = log_expenditure_response.json["data"]["activities"][
        "logExpenditure"
    ]["id"]
    return expenditure_id


class TestApiAdminQueries(BaseTest):
    def setUp(self):
        super().setUp()

        oauth2_client = OAuth2Client.create_client(
            name="test", redirect_uris="http://localhost:3000"
        )
        self.assertIsNotNone(oauth2_client)
        self.client_id = oauth2_client.get_client_id()
        self.client_secret = oauth2_client.secret
        self.api_key = (
            "012345678901234567890123456789012345678901234567890123456789"
        )
        ph = PasswordHasher()
        ThirdPartyApiKeyFactory.create(
            client=oauth2_client, api_key=ph.hash(self.api_key)
        )

        self.company_id = _software_registration(
            self, usual_name="Test", siren="123456789"
        )
        self.company_id_2 = _software_registration(
            self, usual_name="Test2", siren="987654321"
        )
        _sync_employments(self)
        self.user_admin_id = _get_user_id(self, self.employment_admin_id)
        self.user_employee_id = _get_user_id(self, self.employment_employee_id)

        Employment.query.update(
            {"validation_status": EmploymentRequestValidationStatus.APPROVED}
        )
        db.session.commit()
        self.access_token = _get_access_token(self, self.employment_admin_id)

        company_unlinked = CompanyFactory.create(
            usual_name=f"Another Comp", siren=f"00000404"
        )
        self.company_unlinked_id = company_unlinked.id

    def test_create_vehicle_success(self):
        _create_vehicle_success(self)

    def test_edit_vehicle_success(self):
        vehicle_id = _create_vehicle_success(self)
        edit_vehicle_response = test_post_graphql_unexposed(
            query=ApiRequests.edit_vehicle,
            variables={
                "id": vehicle_id,
                "alias": "My Little Pony",
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(edit_vehicle_response.status_code, 200)
        if "errors" in edit_vehicle_response.json:
            self.fail(
                f"Edit vehicle returned an error: {edit_vehicle_response.json}"
            )

    def test_terminate_vehicle_success(self):
        vehicle_id = _create_vehicle_success(self)
        terminate_vehicle_response = test_post_graphql_unexposed(
            query=ApiRequests.terminate_vehicle,
            variables={"id": vehicle_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(terminate_vehicle_response.status_code, 200)
        if "errors" in terminate_vehicle_response.json:
            self.fail(
                f"Terminate vehicle returned an error: {terminate_vehicle_response.json}"
            )

    def test_create_address_success(self):
        _create_address_success(self)

    def test_edit_address_success(self):
        address_id = _create_address_success(self)
        edit_address_response = test_post_graphql_unexposed(
            query=ApiRequests.edit_address,
            variables={
                "companyKnownAddressId": address_id,
                "alias": "Santa Claus",
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(edit_address_response.status_code, 200)
        if "errors" in edit_address_response.json:
            self.fail(
                f"Edit address returned an error: {edit_address_response.json}"
            )

    def test_terminate_address_success(self):
        address_id = _create_address_success(self)
        terminate_address_response = test_post_graphql_unexposed(
            query=ApiRequests.terminate_address,
            variables={"companyKnownAddressId": address_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(terminate_address_response.status_code, 200)
        if "errors" in terminate_address_response.json:
            self.fail(
                f"Terminate address returned an error: {terminate_address_response.json}"
            )

    def test_edit_company_settings_success(self):
        edit_company_settings_response = test_post_graphql_unexposed(
            query=ApiRequests.edit_company_settings,
            variables={"companyId": self.company_id, "allowTeamMode": True},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(edit_company_settings_response.status_code, 200)
        if "errors" in edit_company_settings_response.json:
            self.fail(
                f"Edit company settings returned an error: {edit_company_settings_response.json}"
            )

    def test_create_employment_success(self):
        _create_employment_success(self)

    def test_terminate_employment_success(self):
        _active_employment(self, self.employment_admin_id_2)

        terminate_employment_response = test_post_graphql(
            query=ApiRequests.terminate_employment,
            variables={"employmentId": self.employment_admin_id_2},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        print(terminate_employment_response.json)
        self.assertEqual(terminate_employment_response.status_code, 200)
        if "errors" in terminate_employment_response.json:
            self.fail(
                f"Terminate employment returned an error: {terminate_employment_response.json}"
            )

    def test_change_employee_role_success(self):
        employment_id = _create_employment_success(self)

        change_employee_role_response = test_post_graphql(
            query=ApiRequests.change_employee_role,
            variables={"employmentId": employment_id, "hasAdminRights": True},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(change_employee_role_response.status_code, 200)
        if "errors" in change_employee_role_response.json:
            self.fail(
                f"Change employee role returned an error: {change_employee_role_response.json}"
            )

    def test_send_invite_reminder_success(self):
        employment_id = _create_employment_success(self)

        send_reminder_response = test_post_graphql(
            query=ApiRequests.send_invite_reminder,
            variables={"employmentId": employment_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(send_reminder_response.status_code, 200)
        if "errors" in send_reminder_response.json:
            self.fail(
                f"Send invite reminder returned an error: {send_reminder_response.json}"
            )

    def test_create_mission_success(self):
        _create_mission_success(self)

    def test_log_activity_success(self):
        mission_id = _create_mission_success(self)

        _log_activity_success(self, mission_id, self.user_employee_id)

    def test_log_location_success(self):
        mission_id = _create_mission_success(self)
        address_id = _create_address_success(self)

        log_location_response = test_post_graphql(
            query=ApiRequests.log_location,
            variables={
                "missionId": mission_id,
                "type": "mission_start_location",
                "companyKnownAddressId": address_id,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(log_location_response.status_code, 200)
        if "errors" in log_location_response.json:
            self.fail(
                f"Log location returned an error: {log_location_response.json}"
            )

    def test_log_expenditure_success(self):
        expenditure_id = _log_expenditure_success(self)
        self.assertIsNotNone(expenditure_id)

    def test_cancel_expenditure_success(self):
        expenditure_id = _log_expenditure_success(self)

        cancel_expenditure_response = test_post_graphql(
            query=ApiRequests.cancel_expenditure,
            variables={
                "expenditureId": expenditure_id,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(cancel_expenditure_response.status_code, 200)
        if "errors" in cancel_expenditure_response.json:
            self.fail(
                f"Cancel expenditure returned an error: {cancel_expenditure_response.json}"
            )

    def test_end_mission_success(self):
        mission_id = _create_mission_success(self)
        _end_mission_success(self, mission_id, self.user_employee_id)

    def test_validate_mission_success(self):
        with freeze_time(get_time(how_many_days_ago=0, hour=1)):
            mission_id = _create_mission_success(self)
            _log_activity_success(self, mission_id, self.user_employee_id)

        _end_mission_success(self, mission_id, self.user_employee_id)

        validate_mission_response = test_post_graphql(
            query=ApiRequests.validate_mission,
            variables={
                "missionId": mission_id,
                "usersIds": [self.user_employee_id],
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(validate_mission_response.status_code, 200)
        if "errors" in validate_mission_response.json:
            self.fail(
                f"Validate mission returned an error: {validate_mission_response.json}"
            )

    def test_log_comment_success(self):
        mission_id = _create_mission_success(self)

        _log_comment_success(self, mission_id)

    def test_cancel_comment_success(self):
        mission_id = _create_mission_success(self)
        comment_id = _log_comment_success(self, mission_id)

        cancel_comment_response = test_post_graphql(
            query=ApiRequests.cancel_comment,
            variables={
                "commentId": comment_id,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(cancel_comment_response.status_code, 200)
        if "errors" in cancel_comment_response.json:
            self.fail(
                f"Cancel comment returned an error: {cancel_comment_response.json}"
            )

    def test_cancel_activity_success(self):
        mission_id = _create_mission_success(self)
        activity_id = _log_activity_success(
            self, mission_id, self.user_employee_id
        )

        cancel_activity_response = test_post_graphql(
            query=ApiRequests.cancel_activity,
            variables={
                "activityId": activity_id,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(cancel_activity_response.status_code, 200)
        if "errors" in cancel_activity_response.json:
            self.fail(
                f"Cancel activity returned an error: {cancel_activity_response.json}"
            )

    def test_edit_activity_success(self):
        mission_id = _create_mission_success(self)
        activity_id = _log_activity_success(
            self, mission_id, self.user_employee_id
        )

        edit_activity_response = test_post_graphql(
            query=ApiRequests.edit_activity,
            variables={
                "activityId": activity_id,
                "startTime": to_timestamp(datetime.now()),
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(edit_activity_response.status_code, 200)
        if "errors" in edit_activity_response.json:
            self.fail(
                f"Edit activity returned an error: {edit_activity_response.json}"
            )

    def test_update_mission_vehicle_success(self):
        mission_id = _create_mission_success(self)

        update_mission_vehicle_response = test_post_graphql(
            query=ApiRequests.update_mission_vehicle,
            variables={
                "missionId": mission_id,
                "vehicleRegistrationNumber": "123ABC456",
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(update_mission_vehicle_response.status_code, 200)
        if "errors" in update_mission_vehicle_response.json:
            self.fail(
                f"Update mission vehicle returned an error: {update_mission_vehicle_response.json}"
            )

    def test_change_mission_name_success(self):
        mission_id = _create_mission_success(self)

        change_mission_name_response = test_post_graphql(
            query=ApiRequests.change_mission_name,
            variables={
                "missionId": mission_id,
                "name": "New mission name",
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(change_mission_name_response.status_code, 200)
        if "errors" in change_mission_name_response.json:
            self.fail(
                f"Change mission name returned an error: {change_mission_name_response.json}"
            )

    def test_cancel_mission_success(self):
        mission_id = _create_mission_success(self)
        _active_employment(self, self.employment_employee_id)

        cancel_mission_response = test_post_graphql(
            query=ApiRequests.cancel_mission,
            variables={
                "missionId": mission_id,
                "userId": self.user_employee_id,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(cancel_mission_response.status_code, 200)
        if "errors" in cancel_mission_response.json:
            self.fail(
                f"Cancel mission returned an error: {cancel_mission_response.json}"
            )

    def test_query_mission_info(self):
        mission_id = _create_mission_success(self)

        query_mission_response = test_post_graphql(
            query=ApiRequests.query_mission,
            variables={"id": mission_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(query_mission_response.status_code, 200)
        if "errors" in query_mission_response.json:
            self.fail(
                f"Query mission returned an error: {query_mission_response.json}"
            )

    def test_query_user_info(self):
        query_user_response = test_post_graphql(
            query=ApiRequests.query_user,
            variables={"id": self.user_employee_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        print(query_user_response.json)
        self.assertEqual(query_user_response.status_code, 200)
        if "errors" in query_user_response.json:
            self.fail(
                f"Query user returned an error: {query_user_response.json}"
            )

    def test_query_company_info(self):
        query_company_response = test_post_graphql(
            query=ApiRequests.query_company,
            variables={"id": self.company_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        print(query_company_response.json)
        self.assertEqual(query_company_response.status_code, 200)
        if "errors" in query_company_response.json:
            self.fail(
                f"Query company returned an error: {query_company_response.json}"
            )

    def test_export_c1b(self):
        export_c1b_response = test_post_rest(
            "/companies/generate_tachograph_files",
            json={
                "company_ids": [self.company_id],
                "user_ids": [self.user_employee_id],
                "min_date": "2021-12-16",
                "max_date": "2022-02-14",
                "with_digital_signatures": False,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(export_c1b_response.status_code, 200)
