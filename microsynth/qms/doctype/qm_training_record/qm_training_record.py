# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.data import today
from frappe.utils import get_url_to_form
from frappe.model.document import Document
from frappe.desk.form.assign_to import add, clear
from frappe.desk.form.load import get_attachments
from frappe.core.doctype.communication.email import make
from datetime import datetime
from microsynth.microsynth.utils import add_workdays


class QMTrainingRecord(Document):
    pass


@frappe.whitelist()
def create_training_record(trainee, dt, dn, due_date):
    record = frappe.get_doc(
        {
            'doctype': 'QM Training Record',
            'trainee': trainee, 
            'document_type': dt,
            'document_name': dn,
            'due_date': due_date
        })
    record.save(ignore_permissions = True)
    frappe.db.commit()
    full_name = frappe.get_value("User", trainee, "full_name")
    title = frappe.get_value(dt, dn, "title")
    # create assignment to user
    add({
        'doctype': "QM Training Record",
        'name': record.name,
        'assign_to': trainee,
        'description': f"Dear {full_name},<br>You are welcome to attend the training for {dt} {dn} ({title}).",
        'notify': True
    })


@frappe.whitelist()
def get_overview(qm_training_record):
    doc = frappe.get_doc("QM Training Record", qm_training_record)
    if doc.document_type == "QM Document":
        files = get_attachments(doc.document_type, doc.document_name)
        html = frappe.render_template("microsynth/qms/doctype/qm_document/doc_overview.html", {'files': files, 'doc': doc})
    else:
        html = "<p>No data</p>"
    return html


@frappe.whitelist()
def set_signed_on(doc):
    record = frappe.get_doc("QM Training Record", doc)
    record.signed_on = datetime.today()
    # clear assignment
    clear("QM Training Record", doc)
    record.save(ignore_permissions = True)
    frappe.db.commit()    


def get_training_records(qm_document):
    """
    Return a list of all submitted QM Training Records for the given QM Document 
    """
    return frappe.get_all("QM Training Record",
            filters = [['document_name', '=', qm_document], ['docstatus', '=', 1]],
            fields = ['name', 'trainee', 'signed_on', 'signature'])


def send_reminder_before_due_date(workdays=2):
    """
    Send a reminder to trainees whose QM Training Record is due in exactly :param workdays.
    Should be run by a daily cronjob in the early morning:
    40 4 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.qms.doctype.qm_training_record.qm_training_record.send_reminder_before_due_date

    bench execute microsynth.qms.doctype.qm_training_record.qm_training_record.send_reminder_before_due_date
    """
    target_due_date = add_workdays(today(), workdays)
    # Send reminder for all QM Training Record Drafts due in exactly :param workdays
    qmtr_drafts_due_today = frappe.get_all("QM Training Record",
            filters = [['due_date', '=', f'{target_due_date}'], ['docstatus', '=', 0]],
            fields = ['name', 'trainee', 'document_type', 'document_name'])
    for qmtr in qmtr_drafts_due_today:
        first_name = frappe.get_value("User", qmtr['trainee'], "first_name")
        url = get_url_to_form("QM Training Record", qmtr['name'])
        print(url)
        make(
            recipients = qmtr['trainee'],
            cc = "qm@microsynth.ch",
            sender = "qm@microsynth.ch",
            sender_full_name = "QAU",
            subject = f"Last Reminder: Your QM Training Record {qmtr['name']} is due on {target_due_date}",
            content = f"Dear {first_name},<br><br>Your QM Training Record <a href={url}>{qmtr['name']}</a> is due on {target_due_date}. Please sign by the due date.",
            send_email = True
        )