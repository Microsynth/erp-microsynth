# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def get_columns():
    return [
        {"label": "DocType", "fieldname": "doctype", "fieldtype": "Data", "width": 90},
        {"label": "Document ID", "fieldname": "name", "fieldtype": "Dynamic Link", "options": "doctype", "width": 130},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": "Web Order ID", "fieldname": "web_order_id", "fieldtype": "Data", "width": 90},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 125},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
        {"label": "Customer PO No", "fieldname": "po_no", "fieldtype": "Data", "width": 100},
        {"label": "Contact", "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 65},
        {"label": "Contact Name", "fieldname": "contact_display", "fieldtype": "Data", "width": 110},
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 70},
        {"label": "Comments", "fieldname": "comments", "fieldtype": "Int", "width": 80},
        {"label": "Creator", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": "Creation Date", "fieldname": "creation", "fieldtype": "Date", "width": 125},
    ]


def extract_doc_data(doc):
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "status": doc.get("status"),
        "company": doc.get("company"),
        "customer": doc.get("customer") or doc.get("party_name"),
        "customer_name": doc.get("customer_name", ""),
        "po_no": doc.get("po_no", ""),
        "contact_person": doc.get("contact_person"),
        "contact_display": doc.get("contact_display"),
        "posting_date": doc.get("transaction_date") or doc.get("posting_date"),
        "grand_total": doc.get("grand_total"),
        "currency": doc.get("currency"),
        "web_order_id": doc.get("web_order_id") if doc.doctype != "Quotation" else "",
        "creation": doc.get("creation"),
        "owner": doc.get("owner")
    }


def get_data(filters):
    if not filters.get("web_order_id") and not filters.get("document_id") and not filters.get("customer_po_no"):
        return []

    collected_docs = []
    seen_keys = set()  # Track (doctype, name)
    expand_sales_invoice = False  # only expand Sales Invoice if given by filter to avoid seeing too many documents when searching for an intercompany SO/DN.

    def add_doc(doc_dict):
        if doc_dict not in collected_docs:
            collected_docs.append(doc_dict)

    def safe_get_and_traverse(doctype, name):
        key = (doctype, name)
        if key in seen_keys:
            return
        try:
            doc = frappe.get_doc(doctype, name)
            _traverse(doc)
        except frappe.DoesNotExistError:
            pass

    def _traverse(doc):
        key = (doc.doctype, doc.name)
        if key in seen_keys:
            return
        seen_keys.add(key)
        add_doc(extract_doc_data(doc))
        handler = doctype_handlers.get(doc.doctype)
        if handler:
            handler(doc)

    def handle_quotation(doc):
        items = frappe.get_all("Sales Order Item", filters={"prevdoc_docname": doc.name}, fields=["parent"])
        for item in items:
            if item.parent:
                safe_get_and_traverse("Sales Order", item.parent)

    def handle_sales_order(doc):
        so_items = frappe.get_all("Sales Order Item", filters={"parent": doc.name}, fields=["prevdoc_docname"])
        for item in so_items:
            if item.prevdoc_docname:
                safe_get_and_traverse("Quotation", item.prevdoc_docname)

        dn_items = frappe.get_all("Delivery Note Item", filters={"against_sales_order": doc.name}, fields=["parent"])
        for item in dn_items:
            if item.parent:
                safe_get_and_traverse("Delivery Note", item.parent)

        si_items = frappe.get_all("Sales Invoice Item", filters={"sales_order": doc.name}, fields=["parent"])
        for item in si_items:
            if item.parent:
                safe_get_and_traverse("Sales Invoice", item.parent)

    def handle_delivery_note(doc):
        dn_items = frappe.get_all("Delivery Note Item", filters={"parent": doc.name}, fields=["against_sales_order"])
        for item in dn_items:
            if item.against_sales_order:
                safe_get_and_traverse("Sales Order", item.against_sales_order)

        si_items = frappe.get_all("Sales Invoice Item", filters={"delivery_note": doc.name}, fields=["parent"])
        for item in si_items:
            if item.parent:
                safe_get_and_traverse("Sales Invoice", item.parent)

    def handle_sales_invoice(doc):
        # Expand Sales Invoice only if Sales Invoice ID is given by filter
        # to avoid seeing too many documents when searching for an intercompany SO/DN.
        if not expand_sales_invoice:
            return
        si_items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": doc.name},
            fields=["sales_order", "delivery_note"]
        )
        for item in si_items:
            if item.sales_order:
                safe_get_and_traverse("Sales Order", item.sales_order)
            if item.delivery_note:
                safe_get_and_traverse("Delivery Note", item.delivery_note)

    doctype_handlers = {
        "Quotation": handle_quotation,
        "Sales Order": handle_sales_order,
        "Delivery Note": handle_delivery_note,
        "Sales Invoice": handle_sales_invoice
    }

    # Starting point 1: Document ID
    if filters.get("document_id"):
        prefix = filters["document_id"].split("-")[0]
        prefix_to_doctype = {
            "QTN": "Quotation",
            "SO": "Sales Order",
            "DN": "Delivery Note",
            "SI": "Sales Invoice"
        }
        inferred_doctype = prefix_to_doctype.get(prefix)
        if not inferred_doctype:
            frappe.throw("Could not infer DocType from Document ID prefix.<br>Please enter a valid Document ID starting with QTN, SO, DN or SI followed by '-'.")
        if inferred_doctype == "Sales Invoice":
            expand_sales_invoice = True
        filters["doctype"] = inferred_doctype
        filters["web_order_id"] = frappe.get_value(inferred_doctype, filters["document_id"], "web_order_id")
        safe_get_and_traverse(inferred_doctype, filters["document_id"])

    # Starting point 2: Web Order ID
    if filters.get("web_order_id"):
        web_order_id = filters["web_order_id"]
        for doctype in ("Sales Order", "Delivery Note", "Sales Invoice"):
            docs = frappe.get_all(doctype, filters={"web_order_id": web_order_id}, fields=["name"])
            for rec in docs:
                safe_get_and_traverse(doctype, rec.name)

    # Starting point 3: Customer's Purchase Order
    if filters.get("customer_po_no"):
        customer_po_no = filters["customer_po_no"]
        for doctype in ("Sales Order", "Delivery Note", "Sales Invoice"):
            docs = frappe.get_all(doctype, filters={"po_no": customer_po_no}, fields=["name"])
            for rec in docs:
                safe_get_and_traverse(doctype, rec.name)

    collected_docs.sort(key=lambda d: d.get("creation"))

    # Prepare keys to query comment counts in one batch
    doc_keys = [(d["doctype"], d["name"]) for d in collected_docs]

    # Query all comment counts at once
    if doc_keys:
        placeholders = ', '.join(['(%s, %s)'] * len(doc_keys))
        values = [item for pair in doc_keys for item in pair]

        comment_counts = frappe.db.sql(f"""
            SELECT reference_doctype, reference_name, COUNT(*) as count
            FROM `tabComment`
            WHERE comment_type = 'Comment'
            AND (reference_doctype, reference_name) IN ({placeholders})
            GROUP BY reference_doctype, reference_name
        """, values, as_dict=True)

        # Create a quick lookup
        count_map = {
            (row.reference_doctype, row.reference_name): row.count
            for row in comment_counts
        }
    else:
        count_map = {}

    # Attach comment counts to each document
    for doc in collected_docs:
        doc["comments"] = count_map.get((doc["doctype"], doc["name"]), 0)

    return collected_docs


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    return columns, data
