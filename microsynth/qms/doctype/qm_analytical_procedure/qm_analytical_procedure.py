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
            `tabQM Study`.`title`,
            `tabQM Study`.`type`,
            `tabQM Study`.`completion_date`
        FROM `tabQM Study`
        WHERE 
            `tabQM Study`.`document_type` = "QM Analytical Procedure"
            AND `tabQM Study`.`document_name` = "{qmap_id}"
        -- ORDER BY `tabQM Study`.`completion_date`
        ;""", as_dict=True)
    return studies


def import_analytical_procedures(input_file_path, expected_line_length=16):
    """
    bench execute microsynth.qms.doctype.qm_analytical_procedure.qm_analytical_procedure.import_analytical_procedures --kwargs "{'input_file_path': '/mnt/erp_share/JPe/250505_Beispiel_Import_AP.csv'}"
    """
    import csv

    ich_class_mapping = {
        '1': 'I: Identity',
        '2': 'II: Impurity (quantitative)',
        '3': 'III:  Impurity (qualitative)',
        '4': 'IV: Active ingridients (quantitative)',
        'Other': 'Other',
        'NA': 'NA'
    }
    imported_counter = line_counter = 0

    with open(input_file_path) as file:
        print(f"Parsing Analytical Procedures from '{input_file_path}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            line_counter += 1
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue

            customer_name = line[0].strip()  # remove leading and trailing whitespaces
            regulatory_classification = line[1].strip()
            company = line[2].strip()
            process = line[3].strip()
            analyte = line[4].strip()
            matrix = line[5].strip()
            test_instrument = line[6].strip()
            assay_name = line[7].strip()
            description = line[8].strip()
            drug_product_name = line[9].strip()
            ich_class = line[10].strip()
            assay_type = line[11].strip()
            test_method = line[12].strip()
            analytical_steps = line[13].strip()
            current_status = line[14].strip()
            sops = line[15].strip()

            # fetch QM Process
            qm_processes = frappe.get_all('QM Process', filters=[['name', 'LIKE', f'{process}%']], fields=['name'])
            if len(qm_processes) == 1:
                qm_process = qm_processes[0]['name']
            elif len(qm_processes) == 0:
                print(f"Found no QM Process for process '{process}'. Going to continue with the next Analytical Procedure.")
                continue
            elif len(qm_processes) > 1:
                print(f"Found the following {len(qm_processes)} QM Processes for process '{process}': {qm_processes}. Going to continue with the next Analytical Procedure.")
                continue
            
            # create a new QM Analyte if necessary
            if not frappe.db.exists('QM Analyte', analyte):
                qm_analyte = frappe.get_doc({
                    'doctype': 'QM Analyte',
                    'title': analyte
                })
                qm_analyte.insert()
            
            # create a new QM Device Model if necessary
            if not frappe.db.exists('QM Device Model', test_instrument):
                qm_device_model = frappe.get_doc({
                    'doctype': 'QM Device Model',
                    'title': test_instrument
                })
                qm_device_model.insert()
            
            # check ICH class
            if not ich_class in ich_class_mapping:
                print(f"Unknown ICH class '{ich_class}'. Going to continue with the next Analytical Procedure.")
                continue

            # Create QM Analytical Procedure
            qmap_doc = frappe.get_doc({
                'doctype': 'QM Analytical Procedure',
                'regulatory_classification': regulatory_classification,
                'company': company,
                'qm_process': qm_process,
                'analyte': analyte,
                'matrix': matrix,
                'assay_name': assay_name,
                'description': description,
                'drug_product_name': drug_product_name,
                'ich_class': ich_class_mapping[ich_class],
                'type_of_assay': assay_type,
                'method': test_method,
                'current_status': current_status
            })
            # add device model
            qmap_doc.append("device_models", {
                'device_model': test_instrument
            })

            # split analytical_steps and create new QM Analytical Steps if necessary
            qmas_list = analytical_steps.split(';')
            for step in qmas_list:
                if not frappe.db.exists('QM Analytical Step', step):
                    qm_device_model = frappe.get_doc({
                        'doctype': 'QM Analytical Step',
                        'title': step
                    })
                    qm_device_model.insert()
                
                step_entry = {
                    'step': step
                }
                qmap_doc.append("analytical_steps", step_entry)
            
            # Append Customer Name
            if customer_name != 'NA':
                qmap_doc.append("customers", {
                    'customer_name': customer_name
                })
            
            # Fetch and add SOPs
            if sops != 'NA':
                sop_list = sops.split(';')
                for sop in sop_list:
                    valid_qm_docs = frappe.get_all('QM Document', filters=[['name', 'LIKE', f'{sop}%'], ['status', '=', 'Valid']], fields=['name', 'title'])
                    if len(valid_qm_docs) == 0:
                        print(f"Found no Valid QM Document with an ID like '{sop}'. Unable to link.")
                        continue
                    elif len(valid_qm_docs) == 1:
                        qmap_doc.append("qm_documents", {
                            'qm_document': valid_qm_docs[0]['name'],
                            'title': valid_qm_docs[0]['title']
                        })
                    else:
                        print(f"Found {len(valid_qm_docs)} Valid QM Document with an ID like '{sop}': {valid_qm_docs}. Unable to link.")
                        continue

            try:
                qmap_doc.insert()
                qmap_doc.submit()
                imported_counter += 1
            except Exception as err:
                print(f"{line}: Unable to insert and submit: {err}")
                continue

    print(f"Could successfully import {imported_counter}/{line_counter} Analytical Procedures ({round((imported_counter/line_counter)*100, 2)} %).")
