# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

from microsynth.qms.doctype.competency_assignment.competency_assignment import update_competency_assignments_for_trainee

class QMTrainingCourse(Document):
	def on_submit(self):
		if not self.training_template:
			return

		passed_users = {
			participant.user
			for participant in (self.participants or [])
			if participant.user and participant.outcome == "Passed"
		}
		for user in sorted(passed_users):
			update_competency_assignments_for_trainee(user, self.doctype, self.name)
