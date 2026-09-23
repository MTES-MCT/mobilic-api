import os
import tempfile
import unittest
from xml.etree.ElementTree import parse

from app.helpers.junit_report import JUnitResult, write_junit_xml


class TestJUnitReport(unittest.TestCase):
    def test_report_has_file_time_and_outcomes(self):
        class Sample(unittest.TestCase):
            def test_pass(self):
                pass

            def test_fail(self):
                self.fail("intentional failure")

            @unittest.skip("skip reason")
            def test_skip(self):
                pass

        suite = unittest.TestLoader().loadTestsFromTestCase(Sample)
        result = unittest.TextTestRunner(
            resultclass=JUnitResult,
            verbosity=0,
            stream=open(os.devnull, "w"),
        ).run(suite)

        path = os.path.join(tempfile.mkdtemp(), "junit.xml")
        write_junit_xml(result, path)
        cases = {c.get("name"): c for c in parse(path).getroot()}

        self.assertEqual(len(cases), 3)
        for case in cases.values():
            self.assertTrue(case.get("file").endswith("test_junit_report.py"))
            self.assertGreaterEqual(float(case.get("time")), 0)
        self.assertIsNone(cases["test_pass"].find("failure"))
        self.assertIsNotNone(cases["test_fail"].find("failure"))
        self.assertIsNotNone(cases["test_skip"].find("skipped"))
