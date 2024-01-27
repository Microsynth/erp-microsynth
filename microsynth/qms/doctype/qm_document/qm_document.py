# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint

class QMDocument(Document):
    def autoname(self):
        # auto name function
        base_name = "{0} {1}.{2}.{3}.".format(
            self.document_type,
            self.process_number,
            self.subprocess_number,
            self.chapter or "00"
        )
        # find document number
        docs = frappe.db.sql("""
            SELECT `name` 
            FROM `tabQM Document`
            WHERE `name` LIKE "{0}%"
            LIMIT 1;
            """.format(base_name), as_dict=True)
        
        if len(docs) == 0:
            doc = 1
        else:
            doc = cint((docs[0]['name'][len(base_name):]).split("-")[0]) + 1
            
        self.name = "{base}{doc:03d}".format(base=base_name, doc=doc)
        
        return
            
