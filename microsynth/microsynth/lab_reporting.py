# Copyright (c) 2024, Microsynth
# For license information, please see license.txt

import frappe
from frappe.contacts.doctype.address.address import get_address_display
from microsynth.microsynth.utils import get_customer
from frappe.core.doctype.communication.email import make

@frappe.whitelist()
def create_analysis_report(content=None):
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Lab-Reporting-API#create-analysis-report

    bench execute "microsynth.microsynth.lab_reporting.create_analysis_report" --kwargs "{'content': {'sales_order': 'SO-BAL-24027754', 'report_type': 'Mycoplasma', 'contact_person': '215856'}}"
    """
    if not content:
        return {'success': False, 'message': "Please provide content", 'reference': None}

    sample_details = []
    if 'sample_details' in content:
        for sample_detail in content['sample_details']:
            
            # TODO use existing samples from Sales Order #16658
            sample_doc = frappe.get_doc({
                'doctype': 'Sample',
                'sample_name': sample_detail['sample'],
                
            })
            sample_doc.insert()
            
            # Validate values?
            sample_details.append({
                "sample": sample_doc.name,
                "analysis_method": sample_detail['analysis_method'] or '',
                "analysis_result": sample_detail['analysis_result'] or '',
                "comment": sample_detail['comment'] or ''
            })
    try:
        if 'contact_person' in content and content['contact_person'] and (not 'address' in content or not content['address']):
            # get Address from Contact
            address = frappe.get_value("Contact", content['contact_person'], 'address')
        elif content['address']:
            address = content['address']
        else:
            address = ''
        
        if 'contact_person' in content and content['contact_person'] and (not 'customer' in content or not content['customer']):
            # get Address from Contact
            customer = get_customer(content['contact_person'])
        elif content['customer']:
            customer = content['customer']
        else:
            customer = ''

        ar = frappe.get_doc({
            'doctype': 'Analysis Report',
            'sales_order': content['sales_order'] if 'sales_order' in content else '',
            'web_order_id': content['web_order_id'] if 'web_order_id' in content else '',  # will be fetched from the Sales Order if not given
            'report_type': content['report_type'] if 'report_type' in content else '',
            'issue_date': content['issue_date'] if 'issue_date' in content else '',
            'approved_by': content['approved_by'] if 'approved_by' in content else '',
            'customer': customer,
            'contact_person': content['contact_person'] if 'contact_person' in content else '',
            'address': address,
            'address_display': get_address_display(address) if address else '',
            'sample_details': sample_details
        })
        ar.insert()
        ar.submit()
        frappe.db.commit()
        return {'success': True, 'message': 'OK', 'reference': ar.name}
    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}


def send_reports(recipient, cc_mails, analysis_reports):
    """
    bench execute "microsynth.microsynth.lab_reporting.transmit_analysis_reports" --kwargs "{'recipient': 'test@mail.ch', 'cc_mails': ['me@mail.com', 'somebody@mail.com'], 'analysis_reports': ['AR-2400001', 'AR-2400002']}"
    """
    if not recipient:
        return {'success': False, 'message': 'Found no recipient. Unable to send Analysis Reports.'}
    try:
        # TODO: Create Attachements for the given analysis_reports
        make(
                recipients = recipient,
                sender = "info@microsynth.ch",  # TODO: What should be the sender email address?
                cc = cc_mails,
                subject = "Your Analysis Reports",  # TODO: Better subject
                content = "Dear Microsynth Customer,<br><br>please find attached your analysis reports.<br><br>Kind regards,<br>Your Microsynth lab team",  # TODO: Better message
                send_email = True
                # TODO: Attach PDFs
            )
    except Exception as err:
        return {'success': False, 'message': f"Got the following error: {err}"}
    return {'success': True, 'message': f"Successfully send Analysis Report(s) to '{recipient}'"}


@frappe.whitelist()
def transmit_analysis_reports(content=None):
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Lab-Reporting-API#transmit-analysis-reports

    bench execute "microsynth.microsynth.lab_reporting.transmit_analysis_reports" --kwargs "{'content': {'sales_order': 'SO-BAL-24027754', 'web_order_id': '4103829', 'cc_mails': ['me@mail.com', 'somebody@mail.com'], 'analysis_reports': ['AR-2400001', 'AR-2400002']}}"
    """
    if not content:
        return {'success': False, 'message': 'Please provide content'}
    if not 'analysis_reports' in content or not content['analysis_reports']:
        return {'success': False, 'message': 'A non-empty list of Analysis Report IDs is required.'}

    if 'sales_order' in content and content['sales_order']:
        if not frappe.db.exists('Sales Order', content['sales_order']):
            return {'success': False, 'message': f"The given Sales Order '{content['sales_order']}' does not exist in the ERP. Please provide a valid or no Sales Order ID."}
        for report in content['analysis_reports']:
            analysis_report = frappe.get_doc('Analysis Report', report)
            if not analysis_report:
                return {'success': False, 'message': f"Analysis Report '{report}' does not exist in the ERP."}
            if content['sales_order'] != analysis_report.sales_order:
                return {'success': False, 'message': f"Got Sales Order 'content['sales_order']', but Analysis Report '{report}' belongs to Sales Order 'analysis_report.sales_order'."}
        contact_person = frappe.get_value('Sales Order', content['sales_order'], 'contact_person')
        recipient = frappe.get_value('Contact', contact_person, 'email_id')
        return send_reports(recipient, content['cc_mails'], content['analysis_reports'])
    else:
        # no Sales Order -> create list of distinct contact_persons from the given analysis_reports
        reports_per_person = {}
        for report in content['analysis_reports']:
            contact_person = frappe.get_value('Analysis Report', report, 'contact_person')
            if not contact_person:
                return {'success': False, 'message': f"Found no contact_person on the given Analysis Report '{report}'."}
            if contact_person in reports_per_person:
                reports_per_person[contact_person].append(report)
            else:
                reports_per_person[contact_person] = [report]
        if len(reports_per_person) > 1 and 'cc_mails' in content and content['cc_mails'] and len(content['cc_mails']) > 0:
            return {'success': False, 'message': f"Found more than one distinct contact_person and got cc_mails. Are you sure you want to allow this case?"}
        overall_success = True
        for contact_person, analysis_reports in reports_per_person.items():
            recipient = frappe.get_value('Contact', contact_person, 'email_id')
            message = send_reports(recipient, content['cc_mails'], analysis_reports)
            overall_success = overall_success and message['success']
        if overall_success:
            return {'success': True, 'message': "Successfully send all reports"}
        else:
            return {'success': False, 'message': "Unable to send all reports. Some might be send."}