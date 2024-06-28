# Copyright (c) 2024, Microsynth
# For license information, please see license.txt

import frappe
from frappe.contacts.doctype.address.address import get_address_display
from microsynth.microsynth.utils import get_customer

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
            # Validate values?
            sample_details.append({
                "sample": sample_detail['sample'] or '',
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