from datetime import datetime, date

from flask.ctx import AppContext

from app import app, db
from app.domain.certificate_criteria import (
    is_employee_active,
    IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH,
    IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY,
    get_drivers,
    compute_be_active,
    IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT,
    IS_ACTIVE_MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE,
)
from app.domain.log_activities import log_activity
from app.helpers.time import previous_month_period
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    AuthenticatedUserContext,
    EmploymentFactory,
)
from app.tests import BaseTest


class TestCertificateBeActive(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        self.start, self.end = previous_month_period(date(2023, 3, 28))
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_employee_not_active_no_activities(self):
        self.assertFalse(
            is_employee_active(self.company, self.worker, self.start, self.end)
        )

    def test_employee_active_enough_days_with_enough_activities(self):
        # GIVEN employee has enough days with enough activities in the month
        for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
            mission_date = datetime(2023, 2, day)
            with AuthenticatedUserContext(user=self.worker):
                mission = Mission.create(
                    submitter=self.worker,
                    company=self.company,
                    reception_time=mission_date,
                )
                for idx_activity in range(
                    0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                ):
                    log_activity(
                        submitter=self.worker,
                        user=self.worker,
                        mission=mission,
                        type=ActivityType.WORK,
                        switch_mode=True,
                        reception_time=datetime.now(),
                        start_time=datetime(
                            2023, 2, day, 6 + 2 * idx_activity
                        ),
                        end_time=datetime(2023, 2, day, 7 + 2 * idx_activity),
                    )
            db.session.commit()

        # THEN he is active
        self.assertTrue(
            is_employee_active(self.company, self.worker, self.start, self.end)
        )

    def test_employee_not_active_not_enough_days_with_enough_activities(self):
        # GIVEN employee has not enough days with enough activities in the month
        for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH - 1):
            mission_date = datetime(2023, 2, day)
            with AuthenticatedUserContext(user=self.worker):
                mission = Mission.create(
                    submitter=self.worker,
                    company=self.company,
                    reception_time=mission_date,
                )
                for idx_activity in range(
                    0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                ):
                    log_activity(
                        submitter=self.worker,
                        user=self.worker,
                        mission=mission,
                        type=ActivityType.WORK,
                        switch_mode=True,
                        reception_time=datetime.now(),
                        start_time=datetime(
                            2023, 2, day, 6 + 2 * idx_activity
                        ),
                        end_time=datetime(2023, 2, day, 7 + 2 * idx_activity),
                    )
            db.session.commit()

        # THEN he is not active
        self.assertFalse(
            is_employee_active(self.company, self.worker, self.start, self.end)
        )

    def test_employee_not_active_enough_days_with_not_enough_activities(self):
        # GIVEN employee has enough days but without enough activities
        for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
            mission_date = datetime(2023, 2, day)
            with AuthenticatedUserContext(user=self.worker):
                mission = Mission.create(
                    submitter=self.worker,
                    company=self.company,
                    reception_time=mission_date,
                )
                for idx_activity in range(
                    0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY - 1
                ):
                    log_activity(
                        submitter=self.worker,
                        user=self.worker,
                        mission=mission,
                        type=ActivityType.WORK,
                        switch_mode=True,
                        reception_time=datetime.now(),
                        start_time=datetime(
                            2023, 2, day, 6 + 2 * idx_activity
                        ),
                        end_time=datetime(2023, 2, day, 7 + 2 * idx_activity),
                    )
            db.session.commit()

        # THEN he is not active
        self.assertFalse(
            is_employee_active(self.company, self.worker, self.start, self.end)
        )

    def test_employee_active_activity_counted_on_two_days(self):
        # GIVEN worker has activities on two days
        for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH + 1):
            mission_date = datetime(2023, 2, day)
            with AuthenticatedUserContext(user=self.worker):
                mission = Mission.create(
                    submitter=self.worker,
                    company=self.company,
                    reception_time=mission_date,
                )
                log_activity(
                    submitter=self.worker,
                    user=self.worker,
                    mission=mission,
                    type=ActivityType.WORK,
                    switch_mode=True,
                    reception_time=datetime.now(),
                    start_time=datetime(2023, 2, day, 22),
                    end_time=datetime(2023, 2, day + 1, 3),
                )
            db.session.commit()

        # THEN he needs only N + 1 of them to be active
        self.assertTrue(
            is_employee_active(self.company, self.worker, self.start, self.end)
        )

    def test_employee_not_active_different_company(self):
        different_company = CompanyFactory.create()
        different_admin = UserFactory.create(
            post__company=different_company, post__has_admin_rights=True
        )
        EmploymentFactory.create(
            company=different_company,
            submitter=different_admin,
            user=self.worker,
            has_admin_rights=False,
        )

        # GIVEN employee has enough days with enough activities in the month but with another company
        for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
            mission_date = datetime(2023, 2, day)
            with AuthenticatedUserContext(user=self.worker):
                mission = Mission.create(
                    submitter=self.worker,
                    company=different_company,
                    reception_time=mission_date,
                )
                for idx_activity in range(
                    0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                ):
                    log_activity(
                        submitter=self.worker,
                        user=self.worker,
                        mission=mission,
                        type=ActivityType.WORK,
                        switch_mode=True,
                        reception_time=datetime.now(),
                        start_time=datetime(
                            2023, 2, day, 6 + 2 * idx_activity
                        ),
                        end_time=datetime(2023, 2, day, 7 + 2 * idx_activity),
                    )
            db.session.commit()

        # THEN he is active for other company but not for main company
        self.assertTrue(
            is_employee_active(
                different_company, self.worker, self.start, self.end
            )
        )
        self.assertFalse(
            is_employee_active(self.company, self.worker, self.start, self.end)
        )

    def test_get_drivers_no_employees(self):
        # GIVEN a company doesn't have any drivers
        company_without_drivers = CompanyFactory.create()
        UserFactory.create(
            post__company=company_without_drivers, post__has_admin_rights=True
        )
        # THEN we should get 0 drivers
        self.assertEqual(
            0, len(company_without_drivers.get_drivers(self.start, self.end))
        )
        # AND company should not be active
        self.assertFalse(
            compute_be_active(company_without_drivers, self.start, self.end)
        )

    def test_get_drivers_working_admin(self):
        # GIVEN a company doesn't have any drivers but a working admin
        company_without_drivers = CompanyFactory.create()
        admin_without_drivers = UserFactory.create(
            post__company=company_without_drivers, post__has_admin_rights=True
        )
        with AuthenticatedUserContext(user=admin_without_drivers):
            mission = Mission.create(
                submitter=admin_without_drivers,
                company=company_without_drivers,
                reception_time=datetime(2023, 2, 12),
            )
            log_activity(
                submitter=admin_without_drivers,
                user=admin_without_drivers,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=datetime(2023, 2, 12, 6),
                end_time=datetime(2023, 2, 12, 7),
            )
        db.session.commit()
        # THEN the admin is considered a driver
        self.assertEqual(
            1, len(company_without_drivers.get_drivers(self.start, self.end))
        )

    def test_company_not_active_small_size_one_worker_inactive(self):
        # GIVEN a small size company with all workers active except one
        company_small_size = CompanyFactory.create()
        UserFactory.create(
            post__company=company_small_size, post__has_admin_rights=True
        )
        for idx_employee in range(IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT):
            worker = UserFactory.create(
                post__company=company_small_size, post__has_admin_rights=False
            )
            # first employee is not active
            if idx_employee > 0:
                for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
                    mission_date = datetime(2023, 2, day)
                    with AuthenticatedUserContext(user=worker):
                        mission = Mission.create(
                            submitter=worker,
                            company=company_small_size,
                            reception_time=mission_date,
                        )
                        for idx_activity in range(
                            0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                        ):
                            log_activity(
                                submitter=worker,
                                user=worker,
                                mission=mission,
                                type=ActivityType.WORK,
                                switch_mode=True,
                                reception_time=datetime.now(),
                                start_time=datetime(
                                    2023, 2, day, 6 + 2 * idx_activity
                                ),
                                end_time=datetime(
                                    2023, 2, day, 7 + 2 * idx_activity
                                ),
                            )
                    db.session.commit()

        # THEN company is not active
        self.assertFalse(
            compute_be_active(company_small_size, self.start, self.end)
        )

    def test_company_active_small_size(self):
        # GIVEN a small size company with all workers active
        company_small_size = CompanyFactory.create()
        UserFactory.create(
            post__company=company_small_size, post__has_admin_rights=True
        )
        for _ in range(IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT):
            worker = UserFactory.create(
                post__company=company_small_size, post__has_admin_rights=False
            )
            for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
                mission_date = datetime(2023, 2, day)
                with AuthenticatedUserContext(user=worker):
                    mission = Mission.create(
                        submitter=worker,
                        company=company_small_size,
                        reception_time=mission_date,
                    )
                    for idx_activity in range(
                        0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                    ):
                        log_activity(
                            submitter=worker,
                            user=worker,
                            mission=mission,
                            type=ActivityType.WORK,
                            switch_mode=True,
                            reception_time=datetime.now(),
                            start_time=datetime(
                                2023, 2, day, 6 + 2 * idx_activity
                            ),
                            end_time=datetime(
                                2023, 2, day, 7 + 2 * idx_activity
                            ),
                        )
                db.session.commit()

        # THEN company is active
        self.assertTrue(
            compute_be_active(company_small_size, self.start, self.end)
        )

    def test_company_active_big_size_enough_active(self):
        # GIVEN a large size company with enough workers active
        company_large_size = CompanyFactory.create()
        UserFactory.create(
            post__company=company_large_size, post__has_admin_rights=True
        )
        for idx_employee in range(
            IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT * 2
        ):
            worker = UserFactory.create(
                post__company=company_large_size, post__has_admin_rights=False
            )
            # first 3 employees are active
            if idx_employee < IS_ACTIVE_MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE:
                for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
                    mission_date = datetime(2023, 2, day)
                    with AuthenticatedUserContext(user=worker):
                        mission = Mission.create(
                            submitter=worker,
                            company=company_large_size,
                            reception_time=mission_date,
                        )
                        for idx_activity in range(
                            0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                        ):
                            log_activity(
                                submitter=worker,
                                user=worker,
                                mission=mission,
                                type=ActivityType.WORK,
                                switch_mode=True,
                                reception_time=datetime.now(),
                                start_time=datetime(
                                    2023, 2, day, 6 + 2 * idx_activity
                                ),
                                end_time=datetime(
                                    2023, 2, day, 7 + 2 * idx_activity
                                ),
                            )
                    db.session.commit()

        # THEN company is active
        self.assertTrue(
            compute_be_active(company_large_size, self.start, self.end)
        )

    def test_company_active_big_size_not_enough_active(self):
        # GIVEN a large size company with only two workers active
        company_large_size = CompanyFactory.create()
        UserFactory.create(
            post__company=company_large_size, post__has_admin_rights=True
        )
        for idx_employee in range(
            IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT * 2
        ):
            worker = UserFactory.create(
                post__company=company_large_size, post__has_admin_rights=False
            )
            # only first 2 employees are active
            if idx_employee < IS_ACTIVE_MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE - 1:
                for day in range(3, 3 + IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH):
                    mission_date = datetime(2023, 2, day)
                    with AuthenticatedUserContext(user=worker):
                        mission = Mission.create(
                            submitter=worker,
                            company=company_large_size,
                            reception_time=mission_date,
                        )
                        for idx_activity in range(
                            0, IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
                        ):
                            log_activity(
                                submitter=worker,
                                user=worker,
                                mission=mission,
                                type=ActivityType.WORK,
                                switch_mode=True,
                                reception_time=datetime.now(),
                                start_time=datetime(
                                    2023, 2, day, 6 + 2 * idx_activity
                                ),
                                end_time=datetime(
                                    2023, 2, day, 7 + 2 * idx_activity
                                ),
                            )
                    db.session.commit()

        # THEN company is not active
        self.assertFalse(
            compute_be_active(company_large_size, self.start, self.end)
        )
