import re
import frappe

from microsynth.microsynth.invoicing import retransmit_sales_invoices


def parse_communication_id_from_error(error_log_name):
    """
    bench execute microsynth.microsynth.migration.communication.parse_communication_id_from_error \
        --kwargs "{'error_log_name': '37921264a8'}"
    """

    print(f"Fetching Error Log for: {error_log_name}")

    if not frappe.db.exists("Error Log", error_log_name):
        print("Error Log not found")
        return None

    error_doc = frappe.get_doc("Error Log", error_log_name)

    pattern = r"'communication_name'\s*:\s*'([^']+)'"
    match = re.search(pattern, error_doc.error)

    if match:
        communication_id = match.group(1)
        return communication_id
    else:
        print("No communication ID found")
        return None


def get_sales_invoice_id_from_communication(communication_id):
    """
    bench execute microsynth.microsynth.migration.communication.get_sales_invoice_id_from_communication \
        --kwargs "{'communication_id': 'COMMUNICATION_ID'}"
    """

    if not communication_id:
        print("No communication ID provided")
        return None

    communication_doc = frappe.get_doc("Communication", communication_id)
    if communication_doc and communication_doc.reference_doctype == "Sales Invoice":
        return communication_doc.reference_name
    else:
        print(f"Communication ID {communication_id} not found or not a Sales Invoice")
        return None


def find_and_retransmit_failed_sales_invoice_transmissions(error_title, error_message):
    """
    Finds failed sales invoice transmissions based on title and message of Error Logs, and retransmits the Sales Invoices.
    Args:
        error_title (str): The title of the error log to search for.
        error_message (str): The message content of the error log to search for.

    bench execute microsynth.microsynth.migration.communication.find_and_retransmit_failed_sales_invoice_transmissions \
        --kwargs "{'error_title': 'sendmail', 'error_message': '[SSL: CERTIFICATE_VERIFY_FAILED]'}"
    """

    errors = frappe.get_all("Error Log", filters=[
        ['method', '=', error_title],
        ['error', 'like', f'%{error_message}%']
    ], fields=["name"])

    sales_invoice_ids = set()

    for error in errors:
        communication_id = parse_communication_id_from_error(error.name)
        print(f"Parsed Communication ID: {communication_id}")
        sales_invoice_id = get_sales_invoice_id_from_communication(communication_id)
        print(f"found Sales Invoice ID: {sales_invoice_id}")
        print("-----------------------------------------------")
        if sales_invoice_id:
            sales_invoice_ids.add(sales_invoice_id)

    for sales_invoice_id in sales_invoice_ids:
        print(f"Sales Invoice ID to retransmit: {sales_invoice_id}")
    print("-----------------------------------------------")

    retransmit_sales_invoices(sales_invoice_ids)

    print("Processing complete")
