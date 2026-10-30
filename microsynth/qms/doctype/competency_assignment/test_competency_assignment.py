import unittest
from unittest.mock import patch

from microsynth.qms.doctype.competency_assignment import competency_assignment


class TestQMDocumentRequirements(unittest.TestCase):
    def test_only_exact_submitted_signed_document_version_counts(self):
        records = [{"name": "TRAINING-2", "document_name": "SOP 1.1.01.001-02", "signed_on": "2026-10-30"}]
        with patch.object(competency_assignment.frappe, "get_all", return_value=records) as get_all:
            self.assertEqual(
                competency_assignment._get_signed_qm_training_records("employee@example.com", "SOP 1.1.01.001-02"),
                records,
            )

        self.assertIn(["document_name", "=", "SOP 1.1.01.001-02"], get_all.call_args.kwargs["filters"])
        self.assertIn(["docstatus", "=", 1], get_all.call_args.kwargs["filters"])
        self.assertIn(["signed_on", "is", "set"], get_all.call_args.kwargs["filters"])

    def test_missing_trainee_or_document_has_no_records(self):
        with patch.object(competency_assignment.frappe, "get_all") as get_all:
            self.assertEqual(competency_assignment._get_signed_qm_training_records(None, "SOP-02"), [])
            self.assertEqual(competency_assignment._get_signed_qm_training_records("employee@example.com", None), [])
        get_all.assert_not_called()