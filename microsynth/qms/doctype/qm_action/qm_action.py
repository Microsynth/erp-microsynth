# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add, clear
from frappe.utils.data import today
from frappe.utils import get_url_to_form
from frappe.core.doctype.communication.email import make
from microsynth.microsynth.utils import user_has_role, add_workdays


class QMAction(Document):
	pass


@frappe.whitelist()
def create_action(title, responsible_person, dt, dn, qm_process, due_date, action_type, description, notify=False):
    action = frappe.get_doc(
        {
            'doctype': 'QM Action',
            'title': title,
            'responsible_person': responsible_person,
            'document_type': dt,
            'document_name': dn,
            'qm_process': qm_process,
            'initiation_date': today(),
            'due_date': due_date,
            'type': action_type,
            'description': description,
            'status': 'Created'
        })
    action.save(ignore_permissions = True)
    action.submit()
    frappe.db.commit()

    # do not create assignment to user by default, will be assigned when dn enters status "Implementation"
    if notify:
        assign_and_notify(action.name, responsible_person)

    return action.name


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    action = frappe.get_doc("QM Action", doc)
    action.submit()
    frappe.db.commit()
    update_status(action.name, "Created")


@frappe.whitelist()
def set_status(doc, user, status):
    responsible_person = frappe.get_value("QM Action", doc, "responsible_person")
    if not (user == responsible_person or user_has_role(user, "QAU")):
        frappe.throw(f"Only the Responsible Person '{responsible_person}' or QAU is allowed to set a QM Action to Status '{status}', but user = '{user}'.")
    update_status(doc, status)


def update_status(action, status):
    action = frappe.get_doc("QM Action", action)
    if action.status == status:
        return

    # validate status transitions
    if ((action.status == 'Draft' and status == 'Created') or
        (action.status == 'Created' and status == 'Work in Progress') or
        (action.status == 'Work in Progress' and status == 'Completed')
       ):
        if status == 'Completed':
            action.completion_date = today()
            # clear assignment
            clear("QM Action", action.name)
            # notify creator of Source Document Name
            try:
                msg = f"The QM Action {action.name} of your {action.document_type} {action.document_name} was completed by {frappe.session.user}."
                notify_refdoc_creator(action, msg)
            except Exception as err:
                frappe.log_error(f"Unable to notify the creator of the source document of QM Action {action.name} upon Completion:\n{err}", "qm_action.update_status")
        action.status = status
        action.save()
        frappe.db.commit()
    else:
        frappe.throw(f"Update QM Action: Status transition is not allowed {action.status} --> {status}")


def notify_refdoc_creator(action, msg):
    if action.document_name and action.document_type:
        if action.document_type == 'QM Change':
            cc_type = frappe.get_value('QM Change', action.document_name, 'cc_type')
            if cc_type == 'procurement':
                # notification about completed QM Action for QM Change of type procurement need to be send to QAU
                recipient = 'qm@microsynth.ch'
            else:
                recipient = frappe.get_value(action.document_type, action.document_name, "created_by")
        else:
            recipient = frappe.get_value(action.document_type, action.document_name, "created_by")
        if recipient:
            make(
                recipients = recipient,
                sender = 'erp@microsynth.ch',
                sender_full_name = 'Microsynth ERP',
                subject = f"QM Action {action.name}",
                content = msg,
                send_email = True
                )


@frappe.whitelist()
def cancel(action):
    from microsynth.microsynth.utils import force_cancel
    action_doc = frappe.get_doc("QM Action", action)
    if action_doc.status == "Draft":
        force_cancel("QM Action", action_doc.name)
    else:
        try:
            action_doc.status = 'Cancelled'
            action_doc.save()
            action_doc.cancel()
            frappe.db.commit()
        except Exception as err:
            frappe.throw(f"Unable to cancel QM Action {action}:\n{err}")


@frappe.whitelist()
def assign(doc, responsible_person):
    clear("QM Action", doc)
    add({
        'doctype': "QM Action",
        'name': doc,
        'assign_to': responsible_person,
        'notify': False
    })


@frappe.whitelist()
def assign_and_notify(doc, responsible_person):
    clear("QM Action", doc)
    add({
        'doctype': "QM Action",
        'name': doc,
        'assign_to': responsible_person,
        'notify': True
    })


@frappe.whitelist()
def change_responsible_person(user, action, responsible_person, notify=False):
    action_doc = frappe.get_doc("QM Action", action)
    # check that the user has the right to change the responsible person
    if not (user == action_doc.responsible_person or user_has_role(user, "QAU")):
        frappe.throw(f"Only the Responsible Person '{responsible_person}' or QAU is allowed to change the responsible person, but user = '{user}'.")
    # change the responsible person
    action_doc.responsible_person = responsible_person
    action_doc.save()
    # do not create assignment to user by default, will be assigned when parent document enters status "Implementation"
    if notify:
        assign(action, responsible_person)


def send_reminder_before_due_date(workdays=2):
    """
    Send a reminder to the responsible_person of a QM Action that is due in exactly :param workdays, not cancelled and not completed.
    Should be run by a daily cronjob in the early morning:
    42 4 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.qms.doctype.qm_action.qm_action.send_reminder_before_due_date

    bench execute microsynth.qms.doctype.qm_action.qm_action.send_reminder_before_due_date
    """
    target_due_date = add_workdays(today(), workdays)

    qm_actions_to_remind = frappe.get_all("QM Action",
            filters = [['due_date', '=', f'{target_due_date}'], ['docstatus', '!=', 2], ['status', '!=', 'Completed']],
            fields = ['name', 'title', 'responsible_person', 'document_type', 'document_name'])

    for qma in qm_actions_to_remind:
        first_name = frappe.get_value("User", qma['responsible_person'], "first_name")
        url = get_url_to_form("QM Action", qma['name'])
        #print(url)
        make(
            recipients = qma['responsible_person'],
            cc = "qm@microsynth.ch",
            sender = "qm@microsynth.ch",
            sender_full_name = "QAU",
            subject = f"Last Reminder: Your QM Action {qma['name']} is due on {target_due_date.strftime('%d.%m.%Y')}",
            content = f"Dear {first_name},<br><br>Your QM Action <a href={url}>{qma['name']}</a> ({qma['title']}) is due on {target_due_date.strftime('%d.%m.%Y')}. Please complete the task by the due date.",
            send_email = True
        )
