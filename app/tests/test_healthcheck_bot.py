from unittest.mock import patch

from app import app, db
from app.jobs import platform_health_check
from app.jobs.platform_health_check import job_run_platform_health_checks
from app.models import (
    Activity,
    Company,
    Employment,
    Mission,
    RegulationComputation,
    User,
)
from app.seed import UserFactory, EmploymentFactory
from app.services.healthcheck_bot import (
    BOT_COMPANY_NAME,
    create_healthcheck_bot,
    delete_healthcheck_bot,
)
from app.tests import BaseTest
from app.tests.helpers import init_businesses_data, init_regulation_checks_data


class TestHealthcheckBot(BaseTest):
    def setUp(self):
        super().setUp()
        init_businesses_data()
        init_regulation_checks_data()

    def test_create_is_idempotent(self):
        create_healthcheck_bot(nb_employees=2)
        create_healthcheck_bot(nb_employees=2)
        company = Company.query.filter(
            Company.usual_name == BOT_COMPANY_NAME
        ).one()
        self.assertEqual(User.query.count(), 3)
        self.assertEqual(
            Employment.query.filter(
                Employment.company_id == company.id
            ).count(),
            3,
        )

    def test_bot_runs_on_created_account_then_delete_removes_everything(
        self,
    ):
        create_healthcheck_bot(nb_employees=2)

        def post(url, json, headers, timeout):
            response = app.test_client().post(
                url.replace("http://api.test", ""), json=json, headers=headers
            )
            return type(
                "Resp",
                (),
                {
                    "status_code": response.status_code,
                    "text": response.get_data(as_text=True),
                    "json": lambda self: response.get_json(),
                },
            )()

        with patch.dict(
            app.config, {"API_HOST": "http://api.test"}
        ), patch.object(
            platform_health_check.requests, "post", side_effect=post
        ), patch(
            "app.jobs.platform_health_check.send_tchap_message"
        ) as mock_tchap:
            job_run_platform_health_checks()
        mock_tchap.assert_not_called()
        self.assertGreater(Activity.query.count(), 0)

        self.assertTrue(delete_healthcheck_bot())
        for model in (
            User,
            Company,
            Employment,
            Mission,
            Activity,
            RegulationComputation,
        ):
            self.assertEqual(model.query.count(), 0, model.__name__)
        self.assertFalse(delete_healthcheck_bot())

    def test_delete_refuses_company_with_real_members(self):
        bot, company = create_healthcheck_bot(nb_employees=1)
        real_user = UserFactory.create(email="real@test.com")
        EmploymentFactory.create(
            company=company, submitter=bot, user=real_user
        )
        with self.assertRaises(RuntimeError):
            delete_healthcheck_bot()
        self.assertEqual(
            Company.query.filter(
                Company.usual_name == BOT_COMPANY_NAME
            ).count(),
            1,
        )
