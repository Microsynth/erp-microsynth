# -*- coding: utf-8 -*-
# Copyright (c) 2022, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnextswiss.erpnextswiss.attach_pdf import attach_pdf
from frappe.model.document import Document

class StandingQuotation(Document):
    def on_submit(self):
        attach_pdf(doctype='Standing Quotation', docname=self.name, print_format='Standing Quotation')
        return
