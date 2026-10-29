# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

"""Isolated requirement/report regressions; no configured Frappe site is needed."""

import ast
from collections import defaultdict
from html import escape
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from urllib.parse import quote


class Row(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


def load_functions(path, namespace):
    # Keep production function bodies unchanged, replacing only framework imports
    # with an in-memory database boundary so these tests also run outside bench.
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    for node in tree.body:
        node.decorator_list = []
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace


class TestCompetencyMatrix(unittest.TestCase):
    def setUp(self):
        self.rows = defaultdict(list)
        self.add("Employee", name="EMP-1", user_id="trainee")
        self.add("Staff Profile", name="OLD", employee="EMP-1")
        self.add("Staff Profile", name="NEW", employee="EMP-1")
        self.old = self.add("Competency Assignment", name="OLD-ASSIGNMENT", competency="COMP-1-1", parent="OLD", parenttype="Staff Profile")
        self.assignment = self.add("Competency Assignment", name="NEW-ASSIGNMENT", competency="COMP-1-1", parent="NEW", parenttype="Staff Profile", status="Planned", competency_achieved_on=None)
        self.competency = self.add("Competency", name="COMP-1-1", title="Test competency", docstatus=1, status="Valid", prerequisite_types=[], qm_documents=[], trainings=[])
        framework = SimpleNamespace(
            get_all=self.get_all, get_doc=self.get_doc, parse_json=json.loads,
            db=SimpleNamespace(get_value=self.get_value, exists=lambda dt, name: bool(self.get_all(dt, {"name": name}))),
        )
        root = Path(__file__).resolve().parents[2]
        self.functions = {"frappe": framework, "_": lambda text: text}
        load_functions(root / "versioning.py", self.functions)
        self.functions["re"] = re
        load_functions(root / "doctype/competency_assignment/competency_assignment.py", self.functions)
        self.report = {"frappe": framework, "_": lambda text: text, "escape": escape,
                       "get_versioned_documents": self.functions["get_versioned_documents"],
                       "get_url_to_form": lambda doctype, name: f"/desk#Form/{quote(doctype, safe='')}/{quote(name, safe='')}",
                       "get_competency_requirement_details": self.functions["get_competency_requirement_details"]}
        load_functions(Path(__file__).with_name("competency_matrix.py"), self.report)

    def add(self, doctype, **values):
        row = Row(values)
        self.rows[doctype].append(row)
        return row

    def get_all(self, doctype, filters=None, fields=None):
        def matches(row, field, operator, value):
            actual = row.get(field)
            if operator == "=":
                return actual == value
            if operator == "in":
                return actual in value
            if operator == "is":
                return bool(actual) if value == "set" else not actual
            if operator == "like":
                pattern = re.escape(value).replace("%", ".*").replace("_", ".")
                return re.fullmatch(pattern, actual or "") is not None
            raise AssertionError(f"Unsupported filter: {operator}")
        conditions = []
        if isinstance(filters, dict):
            for key, value in filters.items():
                conditions.append((key, *value) if isinstance(value, list) else (key, "=", value))
        else:
            conditions = filters or []
        result = [row for row in self.rows[doctype] if all(matches(row, *condition) for condition in conditions)]
        return [Row({field: row.get(field) for field in fields}) for row in result] if fields else result

    def get_doc(self, doctype, name):
        return next(row for row in self.rows[doctype] if row.name == name)

    def get_value(self, doctype, name_or_filters, field):
        filters = name_or_filters if isinstance(name_or_filters, dict) else {"name": name_or_filters}
        rows = self.get_all(doctype, filters)
        return rows[0].get(field) if rows else None

    def require(self, *types):
        self.competency.prerequisite_types = [Row(competency_prerequisite=value) for value in types]

    def instruction(self, **overrides):
        values = dict(name="CIN-1", trainee="EMP-1", competency_assignment=self.old.name, docstatus=1, instructor="instructor", date="2026-10-01")
        values.update(overrides)
        return self.add("Competency Instruction", **values)

    def document(self, signed=True, **overrides):
        self.competency.qm_documents = [Row(qm_document="SOP-2")]
        self.add("QM Document", name="SOP-1", title="Document title")
        values = dict(name="QMTR-1", trainee="trainee", document_type="QM Document", document_name="SOP-1", signed_on="2026-10-01" if signed else None, docstatus=1)
        values.update(overrides)
        return self.add("QM Training Record", **values)

    def course(self, outcome="Passed", docstatus=1):
        self.competency.trainings = [Row(training_template="TEMPLATE-1")]
        self.add("QM Training Course", name="COURSE-1", training_template="TEMPLATE-1", date="2026-10-01", docstatus=docstatus, int_ext="External", external_trainer="Trainer")
        self.add("QM Training Course Participant", parent="COURSE-1", parenttype="QM Training Course", parentfield="participants", user="trainee", outcome=outcome)

    def details(self, trainee="trainee"):
        return self.functions["get_competency_requirement_details"](self.competency.name, trainee, "EMP-1")

    def html(self, details):
        return self.report["_build_assignment_details_html"](self.assignment, self.competency, details)

    def test_instruction_required_not_implicitly_achieved(self):
        self.require("On-the-Job Instruction")
        self.assertFalse(self.functions["_competency_requirements_met"](self.competency.name, "trainee"))
        self.assertIn("Competency Instruction", self.html(self.details()))

    def test_instruction_reused_for_same_employee_and_exact_competency(self):
        self.require("On-the-Job Instruction")
        self.instruction()
        self.assertEqual([], self.details()["missing"])
        self.assertTrue(self.functions["_competency_requirements_met"](self.competency.name, "trainee"))
        self.assignment.status = "Achieved"
        self.assertIn("CIN-1", self.html(self.details()))

    def test_other_employee_version_and_cancelled_instructions_rejected(self):
        self.require("On-the-Job Instruction")
        for overrides in ({"trainee": "OTHER"}, {"docstatus": 0}, {"docstatus": 2}):
            with self.subTest(overrides=overrides):
                self.rows["Competency Instruction"] = []
                self.instruction(**overrides)
                self.assertTrue(self.details()["missing"])
        self.rows["Competency Instruction"] = []
        self.old.competency = "COMP-1-2"
        self.instruction()
        self.assertTrue(self.details()["missing"])

    def test_older_document_version_is_visible_evidence(self):
        self.require("QM Document")
        self.document()
        details = self.details()
        self.assertEqual([], details["missing"])
        self.assignment.status = "Achieved"
        html = self.html(details)
        for value in ("QMTR-1", "SOP-1", "Document title", "2026-10-01"):
            self.assertIn(value, html)

    def test_unsigned_cancelled_and_unrelated_records_rejected(self):
        self.require("QM Document")
        for overrides in ({"signed_on": None}, {"docstatus": 2}, {"document_name": "SOP-extra-1"}, {"trainee": "OTHER"}):
            with self.subTest(overrides=overrides):
                self.rows["QM Training Record"] = []
                self.document(**overrides)
                self.assertTrue(self.details()["missing"])

    def test_all_requirements_mandatory(self):
        self.require("QM Document", "Training", "On-the-Job Instruction")
        self.document()
        self.course()
        self.assertTrue(self.details()["missing"])
        self.instruction()
        self.assertEqual([], self.details()["missing"])
        self.assertIn("Trainer", self.html(self.details()))

    def test_course_must_be_submitted_and_passed(self):
        self.require("Training")
        for outcome, docstatus in (("Failed", 1), ("Passed", 0), ("Passed", 2)):
            with self.subTest(outcome=outcome, docstatus=docstatus):
                self.rows["QM Training Course"] = []
                self.rows["QM Training Course Participant"] = []
                self.course(outcome, docstatus)
                self.assertTrue(self.details()["missing"])

    def test_configuration_problems_are_explicit(self):
        for types in ((), ("QM Document",), ("Training",), ("Unknown",)):
            with self.subTest(types=types):
                self.require(*types)
                self.assertTrue(self.details()["missing"])

    def test_invalid_competency_and_missing_user_are_explicit(self):
        self.require("QM Document")
        self.document()
        self.competency.status = "Invalid"
        self.assertIn("submitted and Valid", " ".join(self.details()["missing"]))
        self.competency.status = "Valid"
        self.assertIn("no linked User", " ".join(self.details(None)["missing"]))

    def test_inconsistent_status_is_warned_not_modified(self):
        self.require("On-the-Job Instruction")
        self.assignment.status = "Achieved"
        html = self.html(self.details())
        self.assertIn("Data inconsistency", html)
        self.assertIn("submitted instruction", html)
        self.assertEqual("Achieved", self.assignment.status)
        self.instruction()
        self.assignment.status = "Planned"
        html = self.html(self.details())
        self.assertIn("still Planned", html)
        self.assertIn("CIN-1", html)
        self.assertEqual("Planned", self.assignment.status)

    def test_invalid_competency_links_latest_newer_submitted_valid_version(self):
        self.require("On-the-Job Instruction")
        self.instruction()
        self.competency.status = "Invalid"
        self.assignment.status = "Achieved"
        for name, status, docstatus in (
            ("COMP-1-2", "Valid", 1), ("COMP-1-10", "Valid", 1),
            ("COMP-1-11", "Valid", 0), ("COMP-1-12", "Valid", 2),
            ("COMP-1-13", "Invalid", 1), ("COMP-10-20", "Valid", 1),
        ):
            self.add("Competency", name=name, status=status, docstatus=docstatus)
        html = self.html(self.details())
        self.assertIn("This Competency is Invalid", html)
        self.assertIn("A newer submitted, Valid version is available", html)
        self.assertIn('href="/desk#Form/Competency/COMP-1-10"', html)
        self.assertNotIn("not supported by submitted evidence", html)
        self.assertEqual("Achieved", self.assignment.status)

    def test_invalid_competency_without_newer_valid_version(self):
        self.require("On-the-Job Instruction")
        self.competency.status = "Invalid"
        for status in ("Planned", "Achieved"):
            with self.subTest(status=status):
                self.assignment.status = status
                html = self.html(self.details())
                self.assertIn("This Competency is Invalid", html)
                self.assertIn("No newer submitted, Valid version of this Competency was found", html)
                self.assertNotIn("not supported by submitted evidence", html)
                self.assertEqual(status, self.assignment.status)

    def test_serialized_request_preserves_ids_and_reports_evidence(self):
        self.require("On-the-Job Instruction")
        self.instruction()
        html = self.report["get_cell_details"](json.dumps([self.assignment.name]))["html"]
        self.assertIn("CIN-1", html)
        self.assertIn("still Planned", html)

    def test_popup_escapes_dynamic_content(self):
        self.require("On-the-Job Instruction")
        self.competency.title = "<script>alert(1)</script>"
        self.assertNotIn("<script>", self.html(self.details()))

    def test_popup_document_links_include_unfulfilled_references(self):
        self.require("QM Document", "Training", "On-the-Job Instruction")
        self.document()
        self.course()
        self.instruction()
        html = self.html(self.details())
        for doctype, name in (
            ("Competency", "COMP-1-1"), ("Staff Profile", "NEW"),
            ("QM Training Template", "TEMPLATE-1"), ("Competency Instruction", "CIN-1"),
            ("QM Training Record", "QMTR-1"), ("QM Document", "SOP-1"),
            ("QM Training Course", "COURSE-1"),
        ):
            self.assertIn(f'href="/desk#Form/{quote(doctype, safe="")}/{name}"', html)
        self.rows["QM Training Course Participant"] = []
        self.assertIn('href="/desk#Form/QM%20Training%20Template/TEMPLATE-1"', self.html(self.details()))
        self.assertNotIn("#Form/User/Trainer", html)  # External trainers are plain text.

    def test_instructor_and_internal_trainer_are_plain_text(self):
        self.require("Training", "On-the-Job Instruction")
        self.instruction()
        self.course()
        self.rows["QM Training Course"][0].update(int_ext="Internal", internal_trainer="trainer")
        self.add("User", name="instructor", full_name="Instructor Name")
        self.add("User", name="trainer", full_name="Trainer Name")
        html = self.html(self.details())
        self.assertIn("<strong>Instructor:</strong> Instructor Name</li>", html)
        self.assertIn("<strong>Trainer:</strong> Trainer Name</li>", html)
        self.assertNotIn("#Form/User/", html)

    def test_form_links_preserve_framework_url_and_escape_content(self):
        for url in (
            "/desk#Form/QM%20Training%20Record/QMTR-001545",
            "/app/qm-training-record/QMTR-001545",
        ):
            with self.subTest(url=url):
                self.report["get_url_to_form"] = lambda doctype, name: url
                html = self.report["_detail_item"]("QM Training Record", "QMTR-001545", "QM Training Record")
                self.assertIn(f'href="{url}"', html)
                self.assertIn('target="_blank"', html)
        self.report["get_url_to_form"] = lambda doctype, name: '/app/test/a"&b'
        html = self.report["_detail_item"]("<Label>", "<script>", "Test")
        self.assertIn('href="/app/test/a&quot;&amp;b"', html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<Label>", html)


if __name__ == "__main__":
    unittest.main()
