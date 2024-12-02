import unittest
import datetime
from app.models import Employment, Email, Company, EmailType
from app import db
from app.domain.company import find_employee_for_invitation


class TestFindEmployeeForInvitation(unittest.TestCase):
    def setUp(self):
        self.session = db.session

        self.company = Company(name="Test Company")
        self.employment = Employment(
            creation_time=datetime.datetime.now()
            - datetime.timedelta(days=10),
            has_admin_rights=False,
            user_id=None,
            company=self.company,
        )
        self.email = Email(
            type=EmailType.INVITATION, user_id=None, employment=self.employment
        )

        self.session.add(self.company)
        self.session.add(self.employment)
        self.session.add(self.email)
        self.session.commit()

    def tearDown(self):
        self.session.query(Email).delete()
        self.session.query(Employment).delete()
        self.session.query(Company).delete()
        self.session.commit()

    def test_find_employee_for_invitation(self):
        result = find_employee_for_invitation(datetime.datetime.now())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, self.employment.id)


if __name__ == "__main__":
    unittest.main()
