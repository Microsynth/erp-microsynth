# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document

class IntercompanySettings(Document):
    def validate(self):
        # ToDo: validate that one company can only occur once in the settings child table
        pass
