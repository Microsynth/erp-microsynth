# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and Contributors
# See license.txt
from __future__ import unicode_literals

from unittest.mock import Mock, patch
import unittest

import microsynth.qms.doctype.qm_nonconformity.qm_nonconformity as nc_module


class TestQMNonconformity(unittest.TestCase):
    @patch.object(nc_module, "has_open_actions", return_value=False)
    @patch.object(nc_module, "user_has_role")
    def test_completed_critical_deviation_can_only_be_closed_by_qau_when_actions_are_done(self, mock_user_has_role, mock_has_open_actions):
        mock_user_has_role.side_effect = lambda user, role: user == "qau" and role == "QAU"
        doc = Mock()
        doc.nc_type = "Deviation"
        doc.status = "Completed"
        doc.criticality_classification = "critical"
        doc.created_by = "creator"

        with patch.object(nc_module.frappe, "get_doc", return_value=doc):
            self.assertTrue(nc_module.can_close_completed_deviation("NC-1", "qau"))
            self.assertFalse(nc_module.can_close_completed_deviation("NC-1", "creator"))

    @patch.object(nc_module, "has_open_actions", return_value=False)
    @patch.object(nc_module, "user_has_role")
    def test_completed_non_critical_deviation_can_be_closed_by_qau_or_creator_when_actions_are_done(self, mock_user_has_role, mock_has_open_actions):
        mock_user_has_role.side_effect = lambda user, role: user == "qau" and role == "QAU"
        doc = Mock()
        doc.nc_type = "Deviation"
        doc.status = "Completed"
        doc.criticality_classification = "non-critical"
        doc.created_by = "creator"

        with patch.object(nc_module.frappe, "get_doc", return_value=doc):
            self.assertTrue(nc_module.can_close_completed_deviation("NC-1", "qau"))
            self.assertTrue(nc_module.can_close_completed_deviation("NC-1", "creator"))

    @patch.object(nc_module, "has_open_actions", return_value=True)
    @patch.object(nc_module, "user_has_role")
    def test_completed_deviation_cannot_be_closed_while_any_linked_action_is_open(self, mock_user_has_role, mock_has_open_actions):
        mock_user_has_role.side_effect = lambda user, role: user == "qau" and role == "QAU"
        doc = Mock()
        doc.nc_type = "Deviation"
        doc.status = "Completed"
        doc.criticality_classification = "critical"
        doc.created_by = "creator"

        with patch.object(nc_module.frappe, "get_doc", return_value=doc):
            self.assertFalse(nc_module.can_close_completed_deviation("NC-1", "qau"))
            self.assertFalse(nc_module.can_close_completed_deviation("NC-1", "creator"))

    @patch.object(nc_module, "has_open_actions", return_value=True)
    @patch.object(nc_module, "user_has_role")
    def test_completed_non_deviation_cannot_be_closed_while_linked_actions_are_open(self, mock_user_has_role, mock_has_open_actions):
        mock_user_has_role.side_effect = lambda user, role: user == "qau" and role == "QAU"
        doc = Mock()
        doc.nc_type = "Internal Audit"
        doc.status = "Completed"
        doc.criticality_classification = "critical"
        doc.created_by = "creator"

        with patch.object(nc_module.frappe, "get_doc", return_value=doc):
            self.assertFalse(nc_module.can_close_completed_deviation("NC-1", "qau"))
