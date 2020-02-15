from app.tests import BaseTest, UserFactory
from app import app


class TestQueries(BaseTest):
    def setUp(self):
        super().setUp()
        self.user_company1 = UserFactory.create()
        self.company1 = self.user_company1.company
        self.admin_company1 = UserFactory.create(
            company=self.company1, is_company_admin=True
        )

        self.user_company2 = UserFactory.create()
        self.company2 = self.user_company2.company
        self.admin_company2 = UserFactory.create(
            company=self.company2, is_company_admin=True
        )

    def test_user_can_access_himself(self):
        with app.test_client(
            mock_authentication_with_user=self.user_company1
        ) as c:
            response = c.post_graphql(
                """
                query ($id: Int!){
                    user (id: $id) {
                        firstName
                        lastName
                        id
                    }
                }
                """,
                variables=dict(id=self.user_company1.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json.get("errors"))

            user_data = response.json["data"]["user"]
            self.assertDictEqual(
                user_data,
                dict(
                    firstName=self.user_company1.first_name,
                    lastName=self.user_company1.last_name,
                    id=self.user_company1.id,
                ),
            )

    def test_user_can_access_his_company(self):
        with app.test_client(
            mock_authentication_with_user=self.user_company1
        ) as c:
            response = c.post_graphql(
                """
                query ($id: Int!){
                    company (id: $id) {
                        name
                        id
                        users {
                            id
                        }
                    }
                }
                """,
                variables=dict(id=self.company1.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json.get("errors"))

            company_data = response.json["data"]["company"]
            self.assertDictEqual(
                company_data,
                dict(
                    name=self.company1.name,
                    id=self.company1.id,
                    users=company_data["users"],
                ),
            )
            self.assertSetEqual(
                {self.user_company1.id, self.admin_company1.id},
                set([u["id"] for u in company_data["users"]]),
            )

    def test_user_can_customize_return_data(self):
        with app.test_client(
            mock_authentication_with_user=self.user_company1
        ) as c:
            response = c.post_graphql(
                """
                query ($id: Int!){
                    company (id: $id) {
                        name
                        id
                        users {
                            id
                            isCompanyAdmin
                        }
                    }
                }
                """,
                variables=dict(id=self.company1.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json.get("errors"))

            company_data = response.json["data"]["company"]
            self.assertDictEqual(
                company_data,
                dict(
                    name=self.company1.name,
                    id=self.company1.id,
                    users=company_data["users"],
                ),
            )
            self.assertSetEqual(
                {self.user_company1.id, self.admin_company1.id},
                set([u["id"] for u in company_data["users"]]),
            )
            self.assertSetEqual(
                {True, False},
                set([u["isCompanyAdmin"] for u in company_data["users"]]),
            )

    def test_admin_restricted_data(self):
        with app.test_client(
            mock_authentication_with_user=self.user_company1
        ) as c:
            response = c.post_graphql(
                """
                query ($id: Int!){
                    company (id: $id) {
                        name
                        id
                        users {
                            id
                            activities {
                                id
                            }
                        }
                    }
                }
                """,
                variables=dict(id=self.company1.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json.get("errors"))

            company_data = response.json["data"]["company"]
            self.assertNotEqual(
                [user["activities"] for user in company_data["users"]],
                [[], []],
            )

        with app.test_client(
            mock_authentication_with_user=self.admin_company1
        ) as c:
            response = c.post_graphql(
                """
                query ($id: Int!){
                    company (id: $id) {
                        name
                        id
                        users {
                            id
                            activities {
                                id
                            }
                        }
                    }
                }
                """,
                variables=dict(id=self.company1.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json.get("errors"))

            company_data = response.json["data"]["company"]
            self.assertListEqual(
                [user["activities"] for user in company_data["users"]],
                [[], []],
            )

    def test_user_cannot_access_data_from_other_company(self):
        with app.test_client(
            mock_authentication_with_user=self.admin_company1
        ) as c:
            response = c.post_graphql(
                """
                query ($id: Int!){
                    company (id: $id) {
                        name
                        id
                        users {
                            id
                        }
                    }
                }
                """,
                variables=dict(id=self.company2.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json.get("errors"))
            self.assertIsNone(response.json["data"]["company"])

            response = c.post_graphql(
                """
                query ($id: Int!){
                    user (id: $id) {
                        firstName
                        lastName
                        id
                    }
                }
                """,
                variables=dict(id=self.user_company2.id),
            )

            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(response.json.get("errors"))
            self.assertIsNone(response.json["data"]["user"])
