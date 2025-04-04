# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime


class QMAnalyticalProcedure(Document):
    def on_submit(self):
        self.created_by = frappe.session.user
        self.created_on = datetime.today()
        self.save()
        frappe.db.commit()
