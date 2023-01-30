from datetime import datetime

from argon2 import PasswordHasher

from app.helpers.oauth.models import OAuth2Client, ThirdPartyClientEmployment
from app.helpers.time import to_timestamp
from app.models.activity import ActivityType
from app.seed.factories import ThirdPartyApiKeyFactory
from app.tests import BaseTest, test_post_graphql, test_post_graphql_unexposed
from app.tests.helpers import (
    ApiRequests,
    make_authenticated_request,
    make_protected_request,
)


def _software_registration(self):
    software_registration_response = make_protected_request(
        query=ApiRequests.software_registration,
        variables=dict(
            client_id=self.client_id, usual_name="Test", siren="123456789"
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
    self.company_id = company_id


def _sync_employments(self):
    sync_employment_response = make_protected_request(
        query=ApiRequests.sync_employment,
        variables=dict(
            company_id=self.company_id,
            employees=[
                {
                    "firstName": "Prénom_test1",
                    "lastName": "Nom_test1",
                    "email": "email-salarie1@example.com",
                },
                {
                    "firstName": "Prénom_test2",
                    "lastName": "Nom_test2",
                    "email": "email-salarie2@example.com",
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
    self.assertEqual(len(employment_ids), 2)
    self.employment_id = employment_ids[0]["id"]
    self.employment_id_2 = employment_ids[1]["id"]


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


def _get_access_token(self, employment_id):
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


class TestApiEmployeeQueries(BaseTest):
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

        _software_registration(self)
        _sync_employments(self)
        self.user_id = _get_user_id(self, self.employment_id)
        self.user_id_2 = _get_user_id(self, self.employment_id_2)
        self.access_token = _get_access_token(self, self.employment_id)
        self.access_token_2 = _get_access_token(self, self.employment_id_2)
        _dismiss_employment_token(self, self.employment_id_2, self.user_id_2)

    def test_create_mission_fails_with_no_client_id(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={},
        )
        error_message = create_mission_response.json["errors"][0]["message"]
        self.assertEqual(
            "Unable to find a valid cookie or authorization header",
            error_message,
        )

    def test_create_mission_fails_with_wrong_client_id(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={"X-CLIENT-ID": "wrong"},
        )
        error_message = create_mission_response.json["errors"][0]["message"]
        self.assertEqual(
            "Unable to find a valid cookie or authorization header",
            error_message,
        )

    def test_create_mission_fails_with_no_token(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                # No token
            },
        )
        error_message = create_mission_response.json["errors"][0]["message"]
        self.assertEqual(
            "Unable to find a valid cookie or authorization header",
            error_message,
        )

    def test_create_mission_fails_with_wrong_token(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": "wrong",
            },
        )
        error_message = create_mission_response.json["errors"][0]["message"]
        self.assertEqual("Invalid token", error_message)

    def test_create_mission_fails_with_dismissed_token(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token_2,
            },
        )
        error_message = create_mission_response.json["errors"][0]["message"]
        self.assertEqual("Invalid token", error_message)

    def test_log_activity_fails_with_inconsistent_user_id(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(create_mission_response.status_code, 200)
        mission_id = create_mission_response.json["data"]["activities"][
            "createMission"
        ]["id"]

        log_activity_response = test_post_graphql(
            query=ApiRequests.log_activity,
            variables={
                "startTime": to_timestamp(datetime.now()),
                "missionId": mission_id,
                "type": ActivityType.WORK,
                "user_id": self.user_id_2,
                "switch": True,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        print(log_activity_response.json)
        self.assertIsNotNone(log_activity_response.json["errors"])
        # error_message = log_activity_response.json["errors"][0]["message"]

    def test_start_mission(self):
        create_mission_response = test_post_graphql(
            query=ApiRequests.create_mission,
            variables={"companyId": self.company_id},
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(create_mission_response.status_code, 200)
        mission_id = create_mission_response.json["data"]["activities"][
            "createMission"
        ]["id"]

        log_activity_response = test_post_graphql(
            query=ApiRequests.log_activity,
            variables={
                "startTime": to_timestamp(datetime.now()),
                "missionId": mission_id,
                "type": ActivityType.WORK,
                "user_id": self.user_id,
                "switch": True,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(log_activity_response.status_code, 200)

        geo_api_data = {
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

        log_location_response = test_post_graphql(
            query=ApiRequests.log_location,
            variables={
                "missionId": mission_id,
                "type": "mission_start_location",
                "geoApiData": geo_api_data,
            },
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-EMPLOYMENT-TOKEN": self.access_token,
            },
        )
        self.assertEqual(log_location_response.status_code, 200)
