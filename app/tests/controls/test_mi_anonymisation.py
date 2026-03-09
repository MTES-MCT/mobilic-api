import xml.etree.cElementTree as ET
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.helpers.errors import InvalidParamsError
from app.helpers.pdf.control_bulletin import (
    _generate_part_one,
    generate_control_bulletin_pdf,
)
from app.helpers.xml.greco import process_control
from app.seed import ControllerUserFactory
from app.tests.controls import ControlsTestSimple
from app.tests.helpers import make_authenticated_request

SIREN_POLICE = "110014016"
SIREN_POLICE_2 = "120015011"
SIREN_GENDARMERIE = "157000019"

QUERY_CONTROLLER_WITH_MI = """
    query controllerUser($id: Int!) {
        controllerUser(id: $id) {
            id
            isMinistryOfInterior
        }
    }
"""


class TestMIDetection(ControlsTestSimple):
    """Test detection of Ministry of Interior controllers."""

    def setUp(self):
        super().setUp()
        self.mi_controller = ControllerUserFactory.create(
            organizational_unit=f"Police Nationale/{SIREN_POLICE}/DCSP",
            greco_id="RIO-12345",
        )
        self.ctt_controller = ControllerUserFactory.create(
            organizational_unit="DREAL Pays de la Loire",
            greco_id="GRECO-001",
        )
        self.it_controller = ControllerUserFactory.create(
            organizational_unit="DREETS Ile-de-France",
        )

    def test_mi_controller_detected(self):
        self.assertTrue(self.mi_controller._is_mi())

    def test_mi_property_true(self):
        self.assertTrue(self.mi_controller.is_ministry_of_interior)

    def test_ctt_controller_not_mi(self):
        self.assertFalse(self.ctt_controller._is_mi())

    def test_it_controller_not_mi(self):
        self.assertFalse(self.it_controller._is_mi())

    def test_mi_property_false_for_ctt(self):
        self.assertFalse(self.ctt_controller.is_ministry_of_interior)

    def test_siren_alone_is_mi(self):
        controller = ControllerUserFactory.create(
            organizational_unit=SIREN_POLICE,
        )
        self.assertTrue(controller._is_mi())

    def test_siren_in_longer_string_is_mi(self):
        controller = ControllerUserFactory.create(
            organizational_unit=f"MI/{SIREN_POLICE}/Direction",
        )
        self.assertTrue(controller._is_mi())

    def test_second_police_siren_is_mi(self):
        controller = ControllerUserFactory.create(
            organizational_unit=f"PN/{SIREN_POLICE_2}/DCSP",
        )
        self.assertTrue(controller._is_mi())

    def test_gendarmerie_siren_is_mi(self):
        controller = ControllerUserFactory.create(
            organizational_unit=f"GN/{SIREN_GENDARMERIE}/DGGN",
        )
        self.assertTrue(controller._is_mi())

    def test_ministere_interieur_text_pp_is_mi(self):
        controller = ControllerUserFactory.create(
            organizational_unit="MINISTERE INTERIEUR/PP",
        )
        self.assertTrue(controller._is_mi())

    def test_ministere_interieur_text_dgnp_is_mi(self):
        controller = ControllerUserFactory.create(
            organizational_unit="MINISTERE INTERIEUR/DGNP",
        )
        self.assertTrue(controller._is_mi())

    def test_graphql_exposes_is_ministry_of_interior_true(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.mi_controller.id,
            query=QUERY_CONTROLLER_WITH_MI,
            variables=dict(id=self.mi_controller.id),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        data = response["data"]["controllerUser"]
        self.assertTrue(data["isMinistryOfInterior"])

    def test_graphql_exposes_is_ministry_of_interior_false(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.ctt_controller.id,
            query=QUERY_CONTROLLER_WITH_MI,
            variables=dict(id=self.ctt_controller.id),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        data = response["data"]["controllerUser"]
        self.assertFalse(data["isMinistryOfInterior"])


class TestMIPDFAnonymisation(ControlsTestSimple):
    """Test PDF control bulletin anonymisation for MI controllers."""

    def test_mi_controller_signature_uses_greco_id(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"Police Nationale/{SIREN_POLICE}/DCSP",
            greco_id="RIO-12345",
        )
        control = MagicMock()
        control.controller_user = mi_controller
        control.control_type = "mobilic"
        control.control_bulletin = {
            "employments_business_types": {},
            "user_birth_date": "1990-01-01",
        }

        with patch(
            "app.helpers.pdf.control_bulletin.generate_pdf_from_template"
        ) as mock_pdf:
            mock_pdf.return_value = b"pdf"
            _generate_part_one(control)
            call_kwargs = mock_pdf.call_args
            self.assertEqual(
                call_kwargs.kwargs.get("controller_signature")
                or call_kwargs[1].get("controller_signature"),
                "RIO-12345",
            )

    def test_ctt_controller_signature_uses_greco_id(self):
        ctt_controller = ControllerUserFactory.create(
            organizational_unit="DREAL Pays de la Loire",
            greco_id="GRECO-001",
        )
        control = MagicMock()
        control.controller_user = ctt_controller
        control.control_type = "mobilic"
        control.control_bulletin = {
            "employments_business_types": {},
            "user_birth_date": "1990-01-01",
        }

        with patch(
            "app.helpers.pdf.control_bulletin.generate_pdf_from_template"
        ) as mock_pdf:
            mock_pdf.return_value = b"pdf"
            _generate_part_one(control)
            call_kwargs = mock_pdf.call_args
            self.assertEqual(
                call_kwargs.kwargs.get("controller_signature")
                or call_kwargs[1].get("controller_signature"),
                "GRECO-001",
            )

    def test_mi_controller_no_greco_id_uses_dash(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"Police Nationale/{SIREN_POLICE}/DCSP",
            greco_id=None,
        )
        control = MagicMock()
        control.controller_user = mi_controller
        control.control_type = "mobilic"
        control.control_bulletin = {
            "employments_business_types": {},
            "user_birth_date": "1990-01-01",
        }

        with patch(
            "app.helpers.pdf.control_bulletin.generate_pdf_from_template"
        ) as mock_pdf:
            mock_pdf.return_value = b"pdf"
            _generate_part_one(control)
            call_kwargs = mock_pdf.call_args
            self.assertEqual(
                call_kwargs.kwargs.get("controller_signature")
                or call_kwargs[1].get("controller_signature"),
                "-",
            )

    def test_it_controller_signature_uses_name(self):
        it_controller = ControllerUserFactory.create(
            organizational_unit="DREETS Ile-de-France",
            first_name="Jean",
            last_name="Dupont",
        )
        control = MagicMock()
        control.controller_user = it_controller
        control.control_type = "mobilic"
        control.control_bulletin = {
            "employments_business_types": {},
            "user_birth_date": "1990-01-01",
        }

        with patch(
            "app.helpers.pdf.control_bulletin.generate_pdf_from_template"
        ) as mock_pdf:
            mock_pdf.return_value = b"pdf"
            _generate_part_one(control)
            call_kwargs = mock_pdf.call_args
            self.assertEqual(
                call_kwargs.kwargs.get("controller_signature")
                or call_kwargs[1].get("controller_signature"),
                "Dupont Jean",
            )


class TestMIGrecoIdValidation(ControlsTestSimple):
    """Test greco_id validation for MI controllers on BDC generation."""

    def test_mi_controller_without_greco_id_raises_error(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"MI/{SIREN_POLICE}/DCSP",
            greco_id=None,
        )
        control = MagicMock()
        control.controller_user = mi_controller

        with self.assertRaises(InvalidParamsError):
            generate_control_bulletin_pdf(control)

    def test_mi_controller_with_empty_greco_id_raises_error(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"MI/{SIREN_POLICE}/DCSP",
            greco_id="",
        )
        control = MagicMock()
        control.controller_user = mi_controller

        with self.assertRaises(InvalidParamsError):
            generate_control_bulletin_pdf(control)

    def test_non_mi_controller_without_greco_id_no_error(self):
        ctt_controller = ControllerUserFactory.create(
            organizational_unit="DREAL Pays de la Loire",
            greco_id=None,
        )
        self.assertFalse(ctt_controller.is_ministry_of_interior)

        control = MagicMock()
        control.controller_user = ctt_controller

        with patch(
            "app.helpers.pdf.control_bulletin._generate_part_one"
        ) as mock_p1, patch(
            "app.helpers.pdf.control_bulletin._generate_part_two"
        ) as mock_p2, patch(
            "app.helpers.pdf.control_bulletin.generate_pdf_from_list"
        ) as mock_list:
            mock_p1.return_value = b"p1"
            mock_p2.return_value = b"p2"
            mock_list.return_value = b"pdf"
            generate_control_bulletin_pdf(control)


class TestMIXMLAnonymisation(ControlsTestSimple):
    """Test XML GRECO anonymisation for MI controllers."""

    def _build_mock_control(self, controller):
        control = MagicMock()
        control.controller_id = controller.id
        control.creation_time = datetime(2026, 3, 9, 14, 30)
        control.history_start_date = datetime(2026, 3, 1)
        control.history_end_date = datetime(2026, 3, 9)
        control.vehicle_registration_number = "AB-123-CD"
        control.nb_controlled_days = 7
        control.reported_infractions = []
        control.reference = "REF-001"
        control.control_bulletin = {
            "location_department": "",
            "location_commune": "Paris",
            "location_lieu": "Rue de la Paix",
            "transport_type": "interieur",
            "observation": "",
            "is_vehicle_immobilized": False,
        }
        return control

    def test_mi_controller_xml_anonymises_name(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"MI/{SIREN_POLICE}/DCSP",
            greco_id="RIO-12345",
            first_name="Secret",
            last_name="Agent",
        )
        control = self._build_mock_control(mi_controller)
        doc = ET.Element("ValueSpace")

        process_control(control, control.control_bulletin, doc, [])

        xml_str = ET.tostring(doc, encoding="unicode")
        self.assertNotIn("Secret", xml_str)
        self.assertNotIn("Agent", xml_str)
        self.assertIn("-", xml_str)

    def test_mi_controller_xml_filename_uses_greco_id(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"MI/{SIREN_POLICE}/DCSP",
            greco_id="RIO-12345",
            first_name="Secret",
            last_name="Agent",
        )
        control = self._build_mock_control(mi_controller)
        doc = ET.Element("ValueSpace")

        filename = process_control(control, control.control_bulletin, doc, [])

        self.assertNotIn("SA", filename)
        self.assertIn("RIO-12345", filename)

    def test_mi_controller_xml_without_greco_id_raises_error(self):
        mi_controller = ControllerUserFactory.create(
            organizational_unit=f"MI/{SIREN_POLICE}/DCSP",
            greco_id=None,
            first_name="Secret",
            last_name="Agent",
        )
        control = self._build_mock_control(mi_controller)
        doc = ET.Element("ValueSpace")

        with self.assertRaises(InvalidParamsError):
            process_control(control, control.control_bulletin, doc, [])

    def test_non_mi_controller_xml_uses_real_name(self):
        it_controller = ControllerUserFactory.create(
            organizational_unit="DREETS Ile-de-France",
            first_name="Jean",
            last_name="Dupont",
            greco_id="GRECO-001",
        )
        control = self._build_mock_control(it_controller)
        doc = ET.Element("ValueSpace")

        filename = process_control(control, control.control_bulletin, doc, [])

        xml_str = ET.tostring(doc, encoding="unicode")
        self.assertIn("DUPONT", xml_str)
        self.assertIn("Jean", xml_str)
        self.assertIn("JD", filename)
