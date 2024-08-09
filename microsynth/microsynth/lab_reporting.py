# Copyright (c) 2024, Microsynth
# For license information, please see license.txt

import frappe
from frappe.contacts.doctype.address.address import get_address_display
from microsynth.microsynth.utils import get_customer
from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder
from frappe.desk.form.load import get_attachments
from frappe.core.doctype.communication.email import make
import os


def find_sales_orders(web_order_id):
    """
    bench execute microsynth.microsynth.lab_reporting.find_sales_orders --kwargs "{'web_order_id': '9037231'}"
    """
    sales_orders = frappe.get_all("Sales Order", filters=[['web_order_id', '=', web_order_id], ['docstatus', '=', 1]], fields=['name'])
    return sales_orders


def get_sales_order_samples(sales_order):
    """
    bench execute microsynth.microsynth.lab_reporting.get_sales_order_samples --kwargs "{'sales_order': 'SO-BAL-24028200'}"
    """    
    samples_to_return = []
    sales_order_doc = frappe.get_doc("Sales Order", sales_order)

    for sample in sales_order_doc.samples:
        sample_doc = frappe.get_doc("Sample", sample.sample)
        samples_to_return.append({
            "name": sample_doc.name,
            "sample_name": sample_doc.sample_name,
            "sequencing_label_id": sample_doc.sequencing_label,
            "web_id": sample_doc.web_id
        })
   
    return samples_to_return


@frappe.whitelist()
def fetch_sales_order_samples(web_order_id):
    """
    Try to find Sales Order by Web Order Id (there might be multiple!), return Samples

    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Lab-Reporting-API#fetch-sales-order-samples

    bench execute microsynth.microsynth.lab_reporting.fetch_sales_order_samples --kwargs "{'web_order_id': '4124877'}"
    """
    if not web_order_id:
        return {'success': False,
                'message': "Please provide a Web Order ID",
                'sales_order': None,
                'web_order_id': None,
                'samples': None}

    sales_orders = find_sales_orders(web_order_id)

    if not sales_orders or len(sales_orders) == 0:
        return {'success': False,
                'message': f"Found no submitted Sales Order with the given Web Order ID '{web_order_id}' in the ERP.",
                'sales_order': None,
                'web_order_id': None,
                'samples': [] }
    elif len(sales_orders) == 1:
        samples_to_return = get_sales_order_samples(sales_orders[0]['name'])
        return {'success': True,
                'message': "OK",
                'sales_order': sales_orders[0]['name'],
                'web_order_id': web_order_id,
                'samples': samples_to_return}
    else:
        # more than one Sales Order
        return {'success': False,
                'message': f"Found {len(sales_orders)} Sales Order with the given Web Order ID '{web_order_id}' in the ERP.",
                'sales_order': None,
                'web_order_id': None,
                'samples': [] }


@frappe.whitelist()
def create_analysis_report(content=None):
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Lab-Reporting-API#create-analysis-report

    bench execute microsynth.microsynth.lab_reporting.create_analysis_report --kwargs "{'content': {'sales_order': 'SO-BAL-24027754', 'report_type': 'Mycoplasma', 'contact_person': '215856'}}"
    """
    if not content:
        return {'success': False,
                'message': "Please provide content",
                'reference': None}
    samples = []
    matching_samples = []
    if 'sales_order' in content and content['sales_order']:
        if frappe.db.exists('Sales Order', content['sales_order']):
            samples = get_sales_order_samples(content['sales_order'])
        else:
            return {'success': False,
                    'message': f"The given Sales Order '{content['sales_order']}' does not exist in the ERP.",
                    'reference': None}
    elif 'web_order_id' in content and content['web_order_id']:
        # Try to find Sales Order by Web Order Id (there might be multiple!), match Sample by Customer Sample Name (Sample.sample_name)
        message = fetch_sales_order_samples(content['web_order_id'])
        if not message['success']:
            return {'success': False,
                    'message': message['message'],
                    'reference': None}
        samples = message['samples']
    elif 'sample_details' in content and content['sample_details']:  # no Sales Order ID and no Web Order ID given
        for sample_detail in content['sample_details']:
            if 'sample' in sample_detail and sample_detail['sample']:
                if frappe.db.exists('Sample', sample_detail['sample']):
                    sample_doc = frappe.get_doc("Sample", sample_detail['sample'])
                    if 'sample_name' in sample_detail and sample_detail['sample_name']:
                        # compare sample_name
                        if sample_detail['sample_name'] != sample_doc.sample_name:
                            return {'success': False,
                                    'message': f"Sample '{sample_doc.name}' has sample_name '{sample_doc.sample_name}' in the ERP, but got sample_name '{sample_detail['sample_name']}' in sample_details.",
                                    'reference': None}
                    else:
                        return {'success': False,
                                'message': f"Got no sample_name for the following sample (unable to compare with existing Sample): {sample_detail}",
                                'reference': None}
                else:
                    return {'success': False,
                            'message': f"The given Sample '{sample_detail['sample']}' does not exist in the ERP.",
                            'reference': None}
            else:
                # no Sample -> create a sample with the given name
                if 'sample_name' in sample_detail and sample_detail['sample_name']:
                    sample_doc = frappe.get_doc({
                        'doctype': 'Sample',
                        'sample_name': sample_detail['sample_name']
                    })
                    sample_doc.insert()
                    sample_detail['sample'] = sample_doc.name
                else:
                    return {'success': False,
                            'message': f"Got no sample_name for the following sample (unable to create a new sample): {sample_detail}",
                            'reference': None}
            matching_samples.append(sample_detail)
    else:
        return {'success': False,
                'message': "Please provide existing Sample IDs, a Sales Order ID or Web Order ID.",
                'reference': None}
    
    if len(samples) > 0:
        # compare samples from Sales Order with samples_details from request
        if not ('sample_details' in content and content['sample_details']):
            return {'success': False,
                    'message': "Please provide sample_details.",
                    'reference': None}
        for sample_detail in content['sample_details']:
            found = False
            if not 'sample_name' in sample_detail and sample_detail['sample_name']:
                return {'success': False,
                        'message': f"Got no sample_name for the following sample (unable to compare with Sales Order Samples): {sample_detail}",
                        'reference': None}
            for sample in samples:
                # check if sample_name matches and name (ID) matches if given
                if sample['sample_name'] == sample_detail['sample_name'] and (
                    not 'name' in sample_detail or
                    not sample_detail['name'] or
                    sample['name'] == sample_detail['name']):
                        matching_samples.append(sample_detail)
                        found = True
                        break
            if not found:
                return {'success': False,
                        'message': f"The given sample {sample_detail} does not occur on the given or fetched Sales Order.",
                        'reference': None}
    
    if len(matching_samples) != len(content['sample_details']):
        # should not occur?
        return {'success': False,
                'message': f"Found {len(matching_samples)} matching Samples but got {len(content['sample_details'])} sample details.",
                'reference': None}

    sample_details = []

    for sample_detail in matching_samples:
        sample_details.append({
            "sample": sample_detail['name'],
            "reception_date": sample_detail['reception_date'] or '',
            "analysis_date": sample_detail['analysis_date'] or '',
            "analysis_method": sample_detail['analysis_method'] or '',
            "analysis_result": sample_detail['analysis_result'] or '',
            "deviations": sample_detail['analysis_deviations'] or '',
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

        if 'approved_by' in content and content['approved_by']:
            if frappe.db.exists('User', content['approved_by']):
                approver = content['approved_by']
            else:
                query = """SELECT
                        `tabUser`.`name`
                    FROM `tabUser`
                    WHERE `tabUser`.`username` = "{user}"
                    """.format(user=content['approved_by'])
                users = frappe.db.sql(query, as_dict=True)

                if len(users) == 1:
                    approver = users[0]['name']
                else:
                    return {'success': False,
                            'message': f"Found {len(users)} for {content['approved_by']=}",
                            'reference': None}
        else:
            approver = ''

        ar = frappe.get_doc({
            'doctype': 'Analysis Report',
            'sales_order': content['sales_order'] if 'sales_order' in content else '',
            'web_order_id': content['web_order_id'] if 'web_order_id' in content else '',  # will be fetched from the Sales Order if not given
            'report_type': content['report_type'] if 'report_type' in content else '',
            'issue_date': content['issue_date'] if 'issue_date' in content else '',
            'approved_by': approver,
            'customer': customer,
            'contact_person': content['contact_person'] if 'contact_person' in content else '',
            'address': address,
            'address_display': get_address_display(address) if address else '',
            'sample_details': sample_details,
            'comment': content['comment'] if 'comment' in content else '',
            'disclaimer': content['disclaimer'] if 'disclaimer' in content else ''
        })
        ar.insert()
        ar.submit()
        frappe.db.commit()
        return {'success': True,
                'message': 'OK',
                'reference': ar.name}
    except Exception as err:
        return {'success': False,
                'message': err,
                'reference': None}


def create_pdf_attachment(analysis_report):
    """
    Creates the PDF file for a given Analysis Report name and attaches the file to the record in the ERP.
    """
    doctype = format = "Analysis Report"
    name = analysis_report
    #frappe.local.lang = frappe.db.get_value("Analysis Report", name, "language") or 'en'
    title = frappe.db.get_value(doctype, name, "name")
    doctype_folder = create_folder(doctype, "Home")
    title_folder = create_folder(title, doctype_folder)
    filecontent = frappe.get_print(doctype, name, format, doc=None, as_pdf=True, no_letterhead=False)

    save_and_attach(
        content = filecontent,
        to_doctype = doctype,
        to_name = name,
        folder = title_folder,
        hashname = None,
        is_private = True)


def send_reports(recipient, cc_mails, analysis_reports):
    """
    bench execute microsynth.microsynth.lab_reporting.send_reports --kwargs "{'recipient': 'test@mail.ch', 'cc_mails': ['me@mail.com', 'somebody@mail.com'], 'analysis_reports': ['AR-2400010', 'AR-2400011']}"
    """
    if not recipient:
        return {'success': False, 'message': 'Found no recipient. Unable to send Analysis Reports.'}
    try:
        # Create attachements for the given analysis_reports
        all_attachements = []
        for analysis_report in analysis_reports:
            create_pdf_attachment(analysis_report)
            attachments = get_attachments("Analysis Report", analysis_report)
            fid = None
            for a in attachments:
                fid = a['name']
            all_attachements.append({'fid': fid})
            frappe.db.commit()
        make(
                recipients = recipient,
                sender = "info@microsynth.ch",
                sender_full_name = "Microsynth",
                cc = ", ".join(cc_mails),
                subject = f"Your Microsynth analysis {'reports' if len(all_attachements) > 1 else 'report'}",  # TODO: Better subject?
                content = f"Dear Microsynth Customer,<br><br>please find attached your analysis {'reports' if len(all_attachements) > 1 else 'report'}."
                            f"<br><br>Kind regards,<br>Your Microsynth lab team",  # TODO: Better message
                send_email = True,
                attachments = all_attachements
            )
        #print(f"Send an email with the following attachment to '{recipient}': {all_attachements=}")
    except Exception as err:
        return {'success': False, 'message': f"Got the following error: {err}"}
    return {'success': True, 'message': f"Successfully send Analysis Report(s) to '{recipient}'"}


def webshop_upload(contact_id, web_order_id, analysis_reports):
    """
    Write the given Analysis Reports to the path specified in the Microsynth Settings to enable Webshop upload.
    """
    export_path = frappe.get_value("Microsynth Settings", "Microsynth Settings", "webshop_result_files")

    for analysis_report in analysis_reports:
        report_doc = frappe.get_doc("Analysis Report", analysis_report)
        if not web_order_id:
            web_order_id = report_doc.web_order_id
        if not web_order_id:
            frappe.throw(f"Got no Web Order ID and Analysis Report '{analysis_report}' has no Web Order ID. Unable to create a folder.")
        content_pdf = frappe.get_print(
            "Analysis Report", 
            analysis_report, 
            print_format="Analysis Report", 
            as_pdf=True)
        path = f"{export_path}/{contact_id}/{web_order_id}"
        if not os.path.exists(path):
            os.makedirs(path)
        file_path = f"{path}/{analysis_report}.pdf"
        with open(file_path, mode='wb') as file:
            file.write(content_pdf)


@frappe.whitelist()
def transmit_analysis_reports(content=None):
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Lab-Reporting-API#transmit-analysis-reports

    bench execute microsynth.microsynth.lab_reporting.transmit_analysis_reports --kwargs "{'content': {'sales_order': 'SO-BAL-24027754', 'web_order_id': '4103829', 'cc_mails': ['me@mail.com', 'somebody@mail.com'], 'analysis_reports': ['AR-2400001-1', 'AR-2400002']}}"
    bench execute microsynth.microsynth.lab_reporting.transmit_analysis_reports --kwargs "{'content': {'analysis_reports': ['AR-2400003', 'AR-2400002']}}"
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
                return {'success': False, 'message': f"Got Sales Order '{content['sales_order']}', but Analysis Report '{report}' belongs to Sales Order '{analysis_report.sales_order}'."}
        sales_order = frappe.get_doc('Sales Order', content['sales_order'])
        recipient = frappe.get_value('Contact', sales_order.contact_person, 'email_id')
        webshop_upload(sales_order.contact_person, sales_order.web_order_id, content['analysis_reports'])
        # send reports to the contact person of the given Sales Order
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
            webshop_upload(contact_person, None, analysis_reports)
            message = send_reports(recipient, content['cc_mails'] if 'cc_mails' in content else '', analysis_reports)
            overall_success = overall_success and message['success']
        if overall_success:
            return {'success': True, 'message': "Successfully send all reports"}
        else:
            return {'success': False, 'message': "Unable to send all reports. Some might be send."}


@frappe.whitelist()
def set_sample_labels_processed(samples):
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Lab-Reporting-API#set-sample-labels-processed

    bench execute microsynth.microsynth.lab_reporting.set_sample_labels_processed --kwargs "{'samples': ['SAMPLE204574', 'SAMPLE204575']}"
    """
    if not samples:
        return {'success': False, 'message': 'Please provide samples.'}
    sequencing_labels = []
    try:
        for sample in samples:
            sample_doc = frappe.get_doc('Sample', sample)
            seq_label = frappe.get_doc('Sequencing Label', sample_doc.sequencing_label)
            # Check status before setting it
            if seq_label.status not in ['submitted', 'received']:
                return {'success': False, 'message': f"Sequencing Label '{seq_label.name}' of Sample '{sample}' has status '{seq_label.status}'."}
            sequencing_labels.append(seq_label)
        for seq_label in sequencing_labels:
            seq_label.status = 'processed'
            seq_label.save()
    except Exception as err:
        return {'success': False, 'message': f"Got the following error: {err}"}
    return {'success': True, 'message': 'OK'}