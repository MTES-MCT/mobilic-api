from datetime import datetime

from app.models import User
from app.seed import UserFactory
from app.tests import BaseTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)


class TestAccount(BaseTest):
    def setUp(self):
        super().setUp()
        self.initial_first_name = "Tim"
        self.initial_last_name = "Worker"
        self.user = UserFactory.create(
            first_name=self.initial_first_name,
            last_name=self.initial_last_name,
        )
        self.other_user = UserFactory.create(
            first_name="Other",
            last_name="User",
        )

    def test_change_only_first_name(self, time=datetime(2020, 2, 7, 6)):
        new_first_name = "NouveauPrenom"
        make_authenticated_request(
            time=time,
            submitter_id=self.user.id,
            query=ApiRequests.change_name,
            unexposed_query=True,
            variables={
                "userId": self.user.id,
                "newFirstName": new_first_name,
                "newLastName": self.user.last_name,
            },
        )
        user = User.query.get(self.user.id)
        self.assertEqual(user.first_name, new_first_name)
        self.assertEqual(user.last_name, self.initial_last_name)

    def test_change_only_last_name(self, time=datetime(2020, 2, 7, 6)):
        new_last_name = "NouveauNom"
        make_authenticated_request(
            time=time,
            submitter_id=self.user.id,
            query=ApiRequests.change_name,
            unexposed_query=True,
            variables={
                "userId": self.user.id,
                "newLastName": new_last_name,
                "newFirstName": self.user.first_name,
            },
        )
        user = User.query.get(self.user.id)
        self.assertEqual(user.first_name, self.initial_first_name)
        self.assertEqual(user.last_name, new_last_name)

    def test_change_name(self, time=datetime(2020, 2, 7, 6)):
        new_last_name = "NouveauNom"
        new_first_name = "NouveauPrenom"
        make_authenticated_request(
            time=time,
            submitter_id=self.user.id,
            query=ApiRequests.change_name,
            unexposed_query=True,
            variables={
                "userId": self.user.id,
                "newLastName": new_last_name,
                "newFirstName": new_first_name,
            },
        )
        user = User.query.get(self.user.id)
        self.assertEqual(user.first_name, new_first_name)
        self.assertEqual(user.last_name, new_last_name)

    def test_change_role_with_not_admin(self, time=datetime(2020, 2, 7, 6)):
        response = make_authenticated_request(
            time=time,
            submitter_id=self.other_user.id,
            query=ApiRequests.change_name,
            unexposed_query=True,
            variables={
                "userId": self.user.id,
                "newLastName": "test",
                "newFirstName": "test",
            },
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "AUTHORIZATION_ERROR"
        )
