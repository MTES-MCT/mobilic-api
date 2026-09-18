from app.domain.gender import Gender
from app.seed import CompanyFactory, UserFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request

PII_QUERY = """
  query pii($id: Int!) {
    user(id: $id) {
      id
      email
      phoneNumber
      gender
      birthDate
    }
  }
"""

INVITE = """
  mutation invite($userId: Int, $companyId: Int!, $mail: Email) {
    employments {
      createEmployment(userId: $userId, companyId: $companyId, mail: $mail) {
        id
        email
      }
    }
  }
"""

CANCEL = """
  mutation cancel($employmentId: Int!) {
    employments {
      cancelEmployment(employmentId: $employmentId) {
        success
      }
    }
  }
"""

PHONE = "+33611111111"
BIRTH_DATE = "1990-01-01"


class TestUserPiiAccessAuthorization(BaseTest):
    """UserOutput sensitive fields (email, phone, gender, birthDate) are
    readable only by self or an acknowledged common company. Regression
    guard for YWH-PGM10356-265 (createEmployment BOLA)."""

    def setUp(self):
        super().setUp()
        self.company_a = CompanyFactory.create()
        self.admin_a = UserFactory.create(
            post__company=self.company_a, post__has_admin_rights=True
        )
        self.employee_a = UserFactory.create(
            post__company=self.company_a,
            post__has_admin_rights=False,
            phone_number=PHONE,
            gender=Gender.FEMALE,
            france_connect_info={"birthdate": BIRTH_DATE},
        )
        self.stranger = UserFactory.create(
            phone_number=PHONE,
            gender=Gender.MALE,
            france_connect_info={"birthdate": BIRTH_DATE},
        )

    def _read_pii(self, actor, target):
        return make_authenticated_request(
            time=None,
            submitter_id=actor.id,
            query=PII_QUERY,
            variables={"id": target.id},
        )["data"]["user"]

    def _invite(self, admin, company, user_id=None, mail=None):
        variables = {"company_id": company.id}
        if user_id is not None:
            variables["user_id"] = user_id
        if mail is not None:
            variables["mail"] = mail
        return make_authenticated_request(
            time=None,
            submitter_id=admin.id,
            query=INVITE,
            variables=variables,
        )["data"]["employments"]["createEmployment"]

    def test_self_can_read_own_sensitive_fields(self):
        user = self._read_pii(self.employee_a, self.employee_a)
        self.assertEqual(user["email"], self.employee_a.email)
        self.assertEqual(user["phoneNumber"], PHONE)
        self.assertEqual(user["gender"], "female")
        self.assertEqual(user["birthDate"], BIRTH_DATE)

    def test_admin_can_read_sensitive_fields_of_accepted_employee(self):
        user = self._read_pii(self.admin_a, self.employee_a)
        self.assertEqual(user["email"], self.employee_a.email)
        self.assertEqual(user["phoneNumber"], PHONE)
        self.assertEqual(user["gender"], "female")
        self.assertEqual(user["birthDate"], BIRTH_DATE)

    def test_invited_email_stays_visible_via_employment(self):
        invited_email = "future@corp.fr"
        employment = self._invite(
            self.admin_a, self.company_a, mail=invited_email
        )
        self.assertEqual(employment["email"], invited_email)

    def test_pending_invite_does_not_expose_sensitive_fields(self):
        self._invite(self.admin_a, self.company_a, user_id=self.stranger.id)
        user = self._read_pii(self.admin_a, self.stranger)
        self.assertIsNone(user["phoneNumber"])
        self.assertIsNone(user["gender"])
        self.assertIsNone(user["birthDate"])
        self.assertIsNone(user["email"])

    def test_cancelled_invite_does_not_expose_sensitive_fields(self):
        employment = self._invite(
            self.admin_a, self.company_a, user_id=self.stranger.id
        )
        make_authenticated_request(
            time=None,
            submitter_id=self.admin_a.id,
            query=CANCEL,
            variables={"employment_id": employment["id"]},
        )
        user = self._read_pii(self.admin_a, self.stranger)
        self.assertIsNone(user["phoneNumber"])
        self.assertIsNone(user["gender"])
        self.assertIsNone(user["birthDate"])
        self.assertIsNone(user["email"])
