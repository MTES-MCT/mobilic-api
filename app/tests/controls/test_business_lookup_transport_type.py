from datetime import datetime
from unittest.mock import patch

from app import db
from app.controllers.company import find_business
from app.helpers.errors import InvalidParamsError
from app.models import Business, Company
from app.models.business import BusinessType, TransportType
from app.models.controller_control import ControllerControl
from app.services.get_businesses import BusinessData
from app.tests.controls import ControlsTest
from app.tests.helpers import (
    insert_businesses,
    make_authenticated_request,
    ApiRequests,
)


class TestBusinessLookupTransportType(ControlsTest):
    def setUp(self):
        super().setUp()
        if not Business.query.filter(
            Business.transport_type == TransportType.DEM.value
        ).first():
            self._insert_moving_businesses()
        self.control_id = self._create_control(self.employee_1)

    def _insert_moving_businesses(self):
        for business_data in [
            BusinessData(
                id=10,
                transport_type=TransportType.DEM,
                business_type=BusinessType.LONG_DISTANCE,
            ),
            BusinessData(
                id=11,
                transport_type=TransportType.DEM,
                business_type=BusinessType.SHORT_DISTANCE,
            ),
        ]:
            insert_businesses(business_data)
        db.session.commit()

    def _save_control_bulletin(self, transport_type=None):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.save_control_bulletin,
            variables=dict(
                control_id=self.control_id,
                type="mobilic",
                business_type=BusinessType.LONG_DISTANCE.name,
                transport_type=transport_type,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )

    def _sign_up_company(self, transport_type=None):
        with patch(
            "app.controllers.company.siren_api_client.get_siren_info",
            side_effect=Exception("SIREN API unavailable in tests"),
        ):
            return make_authenticated_request(
                time=datetime.now(),
                submitter_id=self.admin_1.id,
                query=ApiRequests.sign_up_company,
                variables=dict(
                    usual_name="Les Gros Bras Corp",
                    siren="123456789",
                    business_type=BusinessType.LONG_DISTANCE.name,
                    transport_type=transport_type,
                ),
                unexposed_query=True,
            )

    def _sign_up_companies(self, transport_type=None):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_1.id,
            query=ApiRequests.sign_up_companies,
            variables=dict(
                siren="123456789",
                companies=[
                    dict(
                        siret="12345678900011",
                        usualName="Cartons & Compagnie",
                        businessType=BusinessType.SHORT_DISTANCE.name,
                        transportType=TransportType.DEM.name,
                    ),
                    dict(
                        siret="12345678900022",
                        usualName="Piano Sur Le Palier",
                        businessType=BusinessType.LONG_DISTANCE.name,
                        transportType=transport_type,
                    ),
                ],
            ),
            unexposed_query=True,
        )

    def _get_business_id(self, transport_type, business_type):
        return (
            Business.query.filter(
                Business.transport_type == transport_type.value,
                Business.business_type == business_type.value,
            )
            .one()
            .id
        )

    def test_save_control_bulletin_with_moving_transport_type(self):
        response = self._save_control_bulletin(
            transport_type=TransportType.DEM.name
        )
        self.assertIsNone(response.get("errors"))
        control = ControllerControl.query.get(self.control_id)
        self.assertEqual(
            control.control_bulletin["business_id"],
            self._get_business_id(
                TransportType.DEM, BusinessType.LONG_DISTANCE
            ),
        )

    def test_save_control_bulletin_without_transport_type_is_rejected(self):
        response = self._save_control_bulletin()
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )
        control = ControllerControl.query.get(self.control_id)
        self.assertIsNone((control.control_bulletin or {}).get("business_id"))

    def test_sign_up_company_with_moving_transport_type(self):
        response = self._sign_up_company(transport_type=TransportType.DEM.name)
        self.assertIsNone(response.get("errors"))
        company = Company.query.get(
            response["data"]["signUp"]["company"]["company"]["id"]
        )
        self.assertEqual(
            company.business.id,
            self._get_business_id(
                TransportType.DEM, BusinessType.LONG_DISTANCE
            ),
        )
        self.assertEqual(
            [e.business.id for e in company.employments],
            [company.business.id],
        )

    def test_sign_up_company_without_transport_type_is_rejected(self):
        response = self._sign_up_company()
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )
        self.assertIsNone(Company.query.filter_by(siren="123456789").first())

    def test_sign_up_companies_without_transport_type_creates_nothing(self):
        response = self._sign_up_companies()
        self.assertIn(
            "Company 2: Transport type is required",
            response["errors"][0]["message"],
        )
        self.assertEqual(Company.query.filter_by(siren="123456789").count(), 0)

    def test_save_control_bulletin_with_unknown_transport_type_is_rejected(
        self,
    ):
        response = self._save_control_bulletin(transport_type="TELEPORTATION")
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )

    def test_find_business_without_transport_type(self):
        with self.assertRaises(InvalidParamsError):
            find_business(BusinessType.LONG_DISTANCE.name, "")
        business = find_business(BusinessType.VTC.name, "")
        self.assertEqual(business.transport_type, TransportType.TRV)
        self.assertEqual(business.business_type, BusinessType.VTC)
        self.assertIsNone(find_business("", ""))
