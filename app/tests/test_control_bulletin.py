from unittest import TestCase

from app.domain.control_bulletin import get_location_info_from_bulletin


class TestGetLocationInfoFromBulletin(TestCase):
    def test_no_bulletin(self):
        result = get_location_info_from_bulletin(None)

        self.assertEqual(("", "", ""), result)

    def test_empty_bulletin(self):
        result = get_location_info_from_bulletin({})

        self.assertEqual(("", "", ""), result)

    def test_location_department_as_json(self):
        bulletin = {
            "location_department": '{"code": "973", "label": "Guyane"}'
        }

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("973", department_code)
        self.assertEqual("Guyane", department_label)
        self.assertEqual("", postal_code)

    def test_location_department_metropole(self):
        bulletin = {"location_department": '{"code": "75", "label": "Paris"}'}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("75", department_code)
        self.assertEqual("Paris", department_label)

    def test_location_department_not_json_falls_back_to_label(self):
        bulletin = {"location_department": "Guyane"}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("", department_code)
        self.assertEqual("Guyane", department_label)

    def test_location_department_json_without_code_falls_back_to_label(self):
        bulletin = {"location_department": '{"label": "Guyane"}'}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("", department_code)
        self.assertEqual('{"label": "Guyane"}', department_label)

    def test_postal_code_extracted_from_commune_parentheses(self):
        bulletin = {"location_commune": "Cayenne (97300)"}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("97300", postal_code)
        self.assertEqual("973", department_code)

    def test_postal_code_extracted_from_lieu(self):
        bulletin = {"location_lieu": "Route de Cayenne 97300"}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("97300", postal_code)
        self.assertEqual("973", department_code)

    def test_postal_code_metropole_uses_two_digit_department(self):
        bulletin = {"location_commune": "Paris (75001)"}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("75001", postal_code)
        self.assertEqual("75", department_code)

    def test_location_department_takes_priority_over_postal_code(self):
        bulletin = {
            "location_department": '{"code": "75", "label": "Paris"}',
            "location_commune": "Cayenne (97300)",
        }

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("75", department_code)
        self.assertEqual("97300", postal_code)

    def test_commune_without_parentheses_is_ignored(self):
        bulletin = {"location_commune": "Cayenne"}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("", postal_code)
        self.assertEqual("", department_code)

    def test_commune_parentheses_not_a_valid_postal_code_is_ignored(self):
        bulletin = {"location_commune": "Cayenne (Guyane)"}

        department_code, department_label, postal_code = (
            get_location_info_from_bulletin(bulletin)
        )

        self.assertEqual("", postal_code)

    def test_no_location_info_at_all(self):
        bulletin = {"siren": "123456789"}

        result = get_location_info_from_bulletin(bulletin)

        self.assertEqual(("", "", ""), result)
