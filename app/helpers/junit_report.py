import inspect
import os
import time
import unittest
from xml.etree.ElementTree import Element, ElementTree, SubElement


class JUnitResult(unittest.TextTestResult):
    """unittest result recording per-test timing for a JUnit XML report."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        self._start = time.perf_counter()
        self._status = "passed"
        self._message = ""
        super().startTest(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._status, self._message = "failure", self._msg(err)

    def addError(self, test, err):
        super().addError(test, err)
        self._status, self._message = "error", self._msg(err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._status, self._message = "skipped", reason

    @staticmethod
    def _msg(err):
        return f"{err[0].__name__}: {err[1]}"

    def stopTest(self, test):
        super().stopTest(test)
        cls = type(test)
        self.records.append(
            {
                "classname": f"{cls.__module__}.{cls.__qualname__}",
                "name": test._testMethodName,
                "file": os.path.relpath(inspect.getfile(cls)),
                "time": time.perf_counter() - self._start,
                "status": self._status,
                "message": self._message,
            }
        )


def write_junit_xml(result, path):
    suite = Element(
        "testsuite", name="flask-test", tests=str(len(result.records))
    )
    for r in result.records:
        case = SubElement(
            suite,
            "testcase",
            classname=r["classname"],
            name=r["name"],
            file=r["file"],
            time=f"{r['time']:.3f}",
        )
        if r["status"] in ("failure", "error"):
            SubElement(case, r["status"], message=r["message"])
        elif r["status"] == "skipped":
            SubElement(case, "skipped", message=r["message"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)
