# Copyright (c) 2024, Microsynth
# For license information, please see license.txt

import os
import re
from datetime import datetime
import traceback
import frappe
from frappe.utils import get_url_to_form
from frappe.core.doctype.communication.email import make
from frappe.contacts.doctype.address.address import get_address_display
from frappe.desk.form.load import get_attachments
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.utils import get_customer
from microsynth.microsynth.utils import validate_sales_order


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

    bench execute microsynth.microsynth.lab_reporting.create_analysis_report --kwargs "{'content': {'sales_order': 'SO-BAL-24028200','web_order_id': '9037231','report_type': 'Mycoplasma','issue_date': '2024-08-09 12:15:13','approved_by': 'JVo','contact_person': '226318','sample_details': [{'sample_name': 'name_A','reception_date': '2024-06-10 09:48:21','analysis_date': '2024-06-10 10:16:07','analysis_method': 'Bla','analysis_result': 'Blub','analysis_deviations': 'No','comment': ''}],'comment': '','disclaimer': 'D'}}"
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
                    not 'sample' in sample_detail or
                    not sample_detail['sample'] or
                    sample['name'] == sample_detail['sample']):
                        if not 'sample' in sample_detail or not sample_detail['sample']:
                            sample_detail['sample'] = sample['name']
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
            "sample": sample_detail['sample'],
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

    bench execute microsynth.microsynth.lab_reporting.create_pdf_attachment --kwargs "{'analysis_report': 'AR-2400001'}"
    """
    doctype = format = "Analysis Report"
    analysis_report_doc = frappe.get_doc("Analysis Report", analysis_report)
    if len(analysis_report_doc.sample_details) == 1:
        sample = analysis_report_doc.sample_details[0].sample
        sample_name = frappe.get_value("Sample", sample, "sample_name")
        print(f"{sample_name=}")
    elif len(analysis_report_doc.sample_details) > 1:
        msg = f"Analysis Report '{analysis_report}' has {len(analysis_report_doc.sample_details)} sample details, but the file naming is only defined for reports with a single sample."
        frappe.log_error(msg, "lab_reporting.create_pdf_attachment")
        frappe.throw(msg)
    else:
        msg = f"Analysis Report '{analysis_report}' has no sample details, but the file naming is only defined for reports with exactly one sample."
        frappe.log_error(msg, "lab_reporting.create_pdf_attachment")
        frappe.throw(msg)
    doctype_folder = create_folder(doctype, "Home")
    title_folder = create_folder(sample_name, doctype_folder)
    print(f"{title_folder=}")
    # TODO: How to set the file name to sample_name?
    filecontent = frappe.get_print(doctype, analysis_report, format, doc=None, as_pdf=True, no_letterhead=False)

    save_and_attach(
        content = filecontent,
        to_doctype = doctype,
        to_name = analysis_report,
        folder = title_folder,
        hashname = None,
        is_private = True)


def send_reports(recipient, cc_mails, analysis_reports):
    """
    bench execute microsynth.microsynth.lab_reporting.send_reports --kwargs "{'recipient': 'test@mail.ch', 'cc_mails': ['me@mail.com', 'somebody@mail.com'], 'analysis_reports': ['AR-2400001']}"
    """
    if not recipient:
        return {'success': False, 'message': 'Found no recipient. Unable to send Analysis Reports.'}
    try:
        report_types = set()
        web_order_ids = set()
        contact_names = set()
        # Create attachments for the given analysis_reports
        all_attachments = []
        for analysis_report_id in analysis_reports:
            analysis_report = frappe.get_doc("Analysis Report", analysis_report_id)
            if analysis_report.report_type:
                report_types.add(analysis_report.report_type)
            if analysis_report.web_order_id:
                web_order_ids.add(analysis_report.web_order_id)
            if analysis_report.contact_display:
                contact_names.add(analysis_report.contact_display)
            create_pdf_attachment(analysis_report.name)
            attachments = get_attachments("Analysis Report", analysis_report.name)
            fid = None
            for a in attachments:
                fid = a['name']
            all_attachments.append({'fid': fid})
            frappe.db.commit()
        if len(contact_names) > 1:
            return {'success': False, 'message': f"The given reports have the following {len(contact_names)} different Contact Persons: {contact_names}"}
        elif len(contact_names) == 0:
            return {'success': False, 'message': "None of the given report(s) have a Contact Person (contact_display)."}
        if len(report_types) > 1:
            return {'success': False, 'message': f"The given reports have the following {len(report_types)} different Report Types: {report_types}"}
        elif len(report_types) == 0:
            return {'success': False, 'message': "None of the given report(s) have a Report Type. Unable to determine an Email Template."}
        else:
            [report_type] = report_types  # tuple unpacking verifies the assumption that the set contains exactly one element (raising ValueError if it has too many or too few elements)
            [contact_display] = contact_names
            web_order_id = " / ".join(list(web_order_ids))
            email_template = frappe.get_doc("Email Template", f"Analysis Report {report_type}")
            rendered_subject = frappe.render_template(email_template.subject, {'web_order_id': web_order_id})
            rendered_message = frappe.render_template(email_template.response, {'contact_display': contact_display})
        make(
                recipients = recipient,
                sender = email_template.sender,
                sender_full_name = email_template.sender_full_name,
                cc = ", ".join(cc_mails),
                subject = rendered_subject,
                content = rendered_message,
                send_email = True
                # attachments = all_attachments
            )
    except Exception as err:
        err_str = f'{recipient=}, {cc_mails=}, {analysis_reports=}:\nGot the following error: {err}\n{type(err).__name__}\n{traceback.format_exc()}'
        frappe.log_error(err_str, 'lab_reporting.send_reports')
        return {'success': False, 'message': err_str}
    return {'success': True, 'message': f"Successfully send Analysis Report(s) to '{recipient}'"}


def clean_filename(filename):
    """
    Remove leading and trailing spaces.
    Convert other spaces and any character that is not
    dash, word character [a-zA-Z0-9_] or dot to underscores.

    bench execute microsynth.microsynth.lab_reporting.clean_filename --kwargs "{'filename': 'My#fäncy/Sample*nameç1.pdf'}"
    """
    s = filename.strip().replace(" ", "_")
    s = re.sub("[^-a-zA-Z0-9_.]", "_", s)
    if s in ['', '.', '..']:
        return '_'
    return s


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

        analysis_report_doc = frappe.get_doc("Analysis Report", analysis_report)
        if len(analysis_report_doc.sample_details) == 1:
            sample = analysis_report_doc.sample_details[0].sample
            sample_name = frappe.get_value("Sample", sample, "sample_name")
            print(f"{sample_name=}")
        elif len(analysis_report_doc.sample_details) > 1:
            msg = f"Analysis Report '{analysis_report}' has {len(analysis_report_doc.sample_details)} sample details, but the file naming is only defined for reports with a single sample."
            frappe.log_error(msg, "lab_reporting.webshop_upload")
            frappe.throw(msg)
        else:
            msg = f"Analysis Report '{analysis_report}' has no sample details, but the file naming is only defined for reports with exactly one sample."
            frappe.log_error(msg, "lab_reporting.webshop_upload")
            frappe.throw(msg)

        content_pdf = frappe.get_print(
            "Analysis Report", 
            analysis_report, 
            print_format="Analysis Report", 
            as_pdf=True)
        path = f"{export_path}/{contact_id}/{web_order_id}"
        if not os.path.exists(path):
            os.makedirs(path)
        file_path = f"{path}/{clean_filename(sample_name)}.pdf"
        if os.path.isfile(file_path):
            file_path = f"{path}/{clean_filename(sample_name)}_{analysis_report}.pdf"
        if os.path.isfile(file_path):
            frappe.throw(f"The file '{file_path}' does already exist.")
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
        err_str = f'{samples=}:\nGot the following error: {err}\n{type(err).__name__}\n{traceback.format_exc()}'
        frappe.log_error(err_str, 'lab_reporting.set_sample_labels_processed')
        return {'success': False, 'message': err_str}
    return {'success': True, 'message': 'OK'}


def check_mycoplasma_sales_order_completion(verbose=False):
    """
    Find Mycoplasma Sales Orders that have no Delivery Note and are not Closed or Cancelled.
    Check if all their Samples are Processed. If yes, create a Delivery Note in Draft status.

    bench execute microsynth.microsynth.lab_reporting.check_mycoplasma_sales_order_completion --kwargs "{'verbose': True}"
    """
    open_mycoplasma_sales_orders = frappe.db.sql("""
            SELECT `tabSales Order`.`name`,
                `tabSales Order`.`web_order_id`
            FROM `tabSales Order`
            LEFT JOIN `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
            LEFT JOIN `tabDelivery Note Item` ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
                                                 AND `tabDelivery Note Item`.`docstatus` < 2
            LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
                                            AND `tabDelivery Note`.`docstatus` < 2
            WHERE `tabSales Order`.`docstatus` = 1
                AND `tabSales Order`.`status` NOT IN ("Closed", "Completed")
                AND `tabSales Order`.`product_type` = "Genetic Analysis"
                AND `tabSales Order`.`per_delivered` < 100
                AND `tabSales Order Item`.`item_code` IN ('6032', '6033')
                AND (
                    `tabSales Order`.`web_order_id` IS NULL
                    OR NOT EXISTS (
                        SELECT 1
                        FROM `tabDelivery Note`
                        WHERE `tabDelivery Note`.`web_order_id` = `tabSales Order`.`web_order_id`
                            AND `tabDelivery Note`.`docstatus` < 2
                    )
                )
            GROUP BY `tabSales Order`.`name`
            HAVING COUNT(`tabDelivery Note Item`.`parent`) = 0;
        """, as_dict=True)
    if verbose:
        print(f"Found {len(open_mycoplasma_sales_orders)} open Mycoplasma Sales Orders.")

    # check completion of each Mycoplasma Sales Order: Sequencing Labels of this order on processed
    for sales_order in open_mycoplasma_sales_orders:
        if not validate_sales_order(sales_order['name']):
            # validate_sales_order writes to the error log in case of an issue
            if verbose:
                print(f"Sales Order {sales_order['name']} is not valid (check utils.validate_sales_order).")
            continue
        try:
            samples = frappe.db.sql(f"""
                SELECT 
                    `tabSample`.`name`,
                    `tabSequencing Label`.`status`
                FROM `tabSample Link`
                LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
                LEFT JOIN `tabSequencing Label` on `tabSample`.`sequencing_label`= `tabSequencing Label`.`name`
                WHERE
                    `tabSample Link`.`parent` = "{sales_order['name']}"
                    AND `tabSample Link`.`parenttype` = "Sales Order"
                ;""", as_dict=True)

            pending_samples = False
            # check status of label assigned to each sample
            for sample_label in samples:
                if sample_label['status'] != 'processed':
                    pending_samples = True
                    if verbose:
                        print(f"Sales Order {sales_order['name']} has Sample {sample_label['name']} with status {sample_label['status']}.")
                    break
            if pending_samples:
                continue

            # all processed: create delivery
            customer_name = frappe.get_value("Sales Order", sales_order['name'], 'customer')
            customer = frappe.get_doc("Customer", customer_name)

            if customer.disabled:
                frappe.log_error(f"Customer '{customer.name}' of Sales Order '{sales_order['name']}' is disabled. Cannot create a Delivery Note.", "lab_reporting.check_mycoplasma_sales_order_completion")
                continue
            
            # create Delivery Note (leave on draft: submitted in a batch process later on)
            dn_content = make_delivery_note(sales_order['name'])
            dn = frappe.get_doc(dn_content)
            company = frappe.get_value("Sales Order", sales_order, "company")
            dn.naming_series = get_naming_series("Delivery Note", company)

            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()
            if verbose:
                print(f"Created Delivery Note {dn.name} for Sales Order {sales_order['name']}.")

        except Exception as err:
            frappe.log_error(f"Cannot create a Delivery Note for Sales Order '{sales_order['name']}': \n{err}", "lab_reporting.check_mycoplasma_sales_order_completion")


def check_submit_mycoplasma_delivery_note(delivery_note):
    """
    Check if the delivery note is eligible for autocompletion and submit it.

    run
    bench execute microsynth.microsynth.lab_reporting.check_submit_mycoplasma_delivery_note --kwargs "{'delivery_note': 'DN-BAL-24050508'}"
    """
    try:
        delivery_note = frappe.get_doc("Delivery Note", delivery_note)

        if delivery_note.docstatus != 0:
            msg = f"Delivery Note '{delivery_note.name}' is not in Draft. docstatus: {delivery_note.docstatus}"
            print(msg)
            frappe.log_error(msg, "lab_reporting.check_submit_mycoplasma_delivery_note")
            return

        sales_orders = []
        for i in delivery_note.items:
            if i.item_code not in ['6032', '6033']:
                print(f"Delivery Note '{delivery_note.name}': Item '{i.item_code}' is not allowed for autocompletion")
                return
            if i.against_sales_order and (i.against_sales_order not in sales_orders):
                sales_orders.append(i.against_sales_order)

        if len(sales_orders) != 1:
            msg = f"Delivery Note '{delivery_note.name}' is derived from {len(sales_orders)} Sales Orders"
            print(msg)
            frappe.log_error(msg, "lab_reporting.check_submit_mycoplasma_delivery_note")
            return

        # Check that the delivery note was created at least 7 days ago
        time_between_insertion = datetime.today() - delivery_note.creation
        if time_between_insertion.days <= 7:
            print(f"Delivery Note '{delivery_note.name}' is not older than 7 days and was created on {delivery_note.creation}")
            return

        # Check that the Delivery Note does not contain a Sample with a Barcode Label associated with more than one Sample
        for sample in delivery_note.samples:
            barcode_label = frappe.get_value("Sample", sample.sample, "sequencing_label")
            samples = frappe.get_all("Sample", filters=[["sequencing_label", "=", barcode_label]], fields=['name', 'web_id', 'creation'])
            if len(samples) > 1:
                # Only log an error
                sample_details = ""
                for s in samples:
                    url = get_url_to_form("Sample", s['name'])
                    sample_details += f"Sample <a href={url}>{s['name']}</a> with Web ID '{s['web_id']}', created {s['creation']}<br>"
                frappe.log_error(f"Delivery Note '{delivery_note.name}' won't be submitted automatically in the ERP, because it contains a Sample with Barcode Label '{barcode_label}' that is used for {len(samples)} different Samples:\n{sample_details}")
                # Create Email Template with the Name and Subject "Mycoplasma Barcode used multiple times", Sender erp@microsynth.ch,
                # Sender Full Name "Microsynth ERP", Recipients SWö, CC Recipients RSu, JPe and the following response?:
                """
                Dear Stefan,

                this is an automatic email to inform you that Delivery Note '{{ delivery_note_name }}' won't be submitted automatically in the ERP, because it contains a Sample with Barcode Label '{{ barcode_label }}' that is used for {{ len_samples }} different Samples:

                {{ sample_details }}

                Please check these Samples. If you are sure that there is no problem, please submit '{{ delivery_note_name }}' manually in the ERP.
                If one of those Samples is on a Sales Order that was not processed and will not be processed, please comment and cancel this Sales Order.

                Best regards,
                Jens
                """
                # email_template = frappe.get_doc("Email Template", "Mycoplasma Barcode used multiple times")
                # values_to_render = {
                #     'delivery_note_name': delivery_note.name,
                #     'barcode_label': barcode_label,
                #     'len_samples': len(samples),
                #     'sample_details': sample_details
                # }
                # rendered_message = frappe.render_template(email_template.response, values_to_render)
                # #non_html_message = rendered_message.replace("<br>","\n")
                # #print(non_html_message)
                # make(
                #     recipients = email_template.recipients,
                #     sender = email_template.sender,
                #     sender_full_name = email_template.sender_full_name,
                #     cc = email_template.cc_recipients,
                #     subject = email_template.subject,
                #     content = rendered_message,
                #     send_email = True
                #     )
                return

        delivery_note.submit()

    except Exception as err:
        frappe.log_error(f"Cannot process Delivery Note '{delivery_note.name}': \n{err}", "lab_reporting.check_submit_mycoplasma_delivery_note")


def submit_mycoplasma_delivery_notes():
    """
    Checks all delivery note drafts of product type sequencing and submits them if eligible.

    bench execute microsynth.microsynth.lab_reporting.submit_mycoplasma_delivery_notes
    """
    delivery_notes = frappe.db.sql(f"""
        SELECT `tabDelivery Note`.`name`
        FROM `tabDelivery Note`
        LEFT JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
        WHERE `tabDelivery Note`.`docstatus` = 0
            AND `tabDelivery Note`.`product_type` = "Genetic Analysis"
            AND `tabDelivery Note Item`.`item_code` IN ('6032', '6033')
        GROUP BY `tabDelivery Note`.`name`
    ;""", as_dict=True)
    #print(f"Found {len(delivery_notes)} Mycoplasma Delivery Note Drafts.")

    for dn in delivery_notes:
        check_submit_mycoplasma_delivery_note(dn.name)
        frappe.db.commit()
