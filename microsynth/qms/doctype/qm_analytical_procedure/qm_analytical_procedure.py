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

    def get_advanced_dashboard(self):
        html = frappe.render_template("microsynth/qms/doctype/qm_analytical_procedure/advanced_dashboard.html",
            {
                'doc': self,
                'studies': get_studies(self.name),
                'qm_documents': self.get_qm_documents()
            })
        return html

    def get_qm_documents(self):
        relating_docs = []
        for doc in self.qm_documents:
            if frappe.get_value("QM Document", doc.qm_document, "status") == "Valid":
                relating_docs.append(doc.qm_document)
            else:
                # try to find the valid version
                without_version = doc.qm_document.split("-")[0]
                valid_docs = frappe.db.sql(f"""
                    SELECT `tabQM Document`.`name`
                    FROM `tabQM Document`
                    WHERE `tabQM Document`.`name` LIKE '{without_version}%'
                        AND `tabQM Document`.`status` = 'Valid';
                    """, as_dict=True)
                if len(valid_docs) == 1:
                    relating_docs.append(valid_docs[0]['name'])
                elif len(valid_docs) > 1:
                    frappe.log_error(f"There seem to be {len(valid_docs)} Valid versions of QM Document LIKE '{without_version}%'.", "qm_document.get_overview")
                else:
                    # no valid version -> take the highest version
                    all_versions = frappe.db.sql(f"""
                    SELECT `tabQM Document`.`name`
                    FROM `tabQM Document`
                    WHERE `tabQM Document`.`name` LIKE '{without_version}%'
                        AND `tabQM Document`.`docstatus` = 1
                    ORDER BY `tabQM Document`.`version` DESC;
                    """, as_dict=True)
                    if len(all_versions) > 0:
                        relating_docs.append(all_versions[0]['name'])
                    else:
                        #frappe.log_error(f"There seem to be no QM Documents LIKE '{without_version}%' with docstatus 1.", "qm_document.get_overview")
                        continue
        return relating_docs


def get_studies(qmap_id):
    """
    """
    studies = frappe.db.sql(f"""
        SELECT 
            `tabQM Study`.`name`,
            `tabQM Study`.`title`
        FROM `tabQM Study`
        WHERE 
            `tabQM Study`.`document_type` = "QM Analytical Procedure"
            AND `tabQM Study`.`document_name` = "{qmap_id}"
        ;""", as_dict=True)
    return studies
