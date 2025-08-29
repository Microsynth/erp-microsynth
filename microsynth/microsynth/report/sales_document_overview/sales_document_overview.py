# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def get_columns():
    return [
        {"label": "DocType", "fieldname": "doctype", "fieldtype": "Data", "width": 85},
        {"label": "Document ID", "fieldname": "name", "fieldtype": "Dynamic Link", "options": "doctype", "width": 125},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": "Web Order ID", "fieldname": "web_order_id", "fieldtype": "Data", "width": 90},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 125},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 90},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": "Contact", "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 65},
        {"label": "Contact Name", "fieldname": "contact_display", "fieldtype": "Data", "width": 160},
        {"label": "Total Amount", "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 70},
        {"label": "Comments", "fieldname": "comments", "fieldtype": "Int", "width": 80},
        {"label": "Creator", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 175},
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
        "contact_person": doc.get("contact_person"),
        "contact_display": doc.get("contact_display"),
        "posting_date": doc.get("transaction_date") or doc.get("posting_date"),
        "total": doc.get("total"),
        "currency": doc.get("currency"),
        "web_order_id": doc.get("web_order_id") if doc.doctype != "Quotation" else "",
        "creation": doc.get("creation"),
        "owner": doc.get("owner")
    }


def get_data(filters):
    if not filters.get("web_order_id") and not filters.get("document_id"):
        return []

    web_order_ids = set()
    collected_docs = []
    seen_keys = set()  # Track (doctype, name)

    def add_doc(doc_dict):
        key = (doc_dict["doctype"], doc_dict["name"])
        if key not in seen_keys:
            collected_docs.append(doc_dict)
            seen_keys.add(key)

    # Case 1: document_id + doctype provided
    if filters.get("document_id"):
        # Try to infer the DocType from the prefix
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

        filters["doctype"] = inferred_doctype
        doc = frappe.get_doc(filters["doctype"], filters["document_id"])
        add_doc(extract_doc_data(doc))

        # Handle Quotation specially
        if filters["doctype"] == "Quotation":
            so_items = frappe.get_all("Sales Order Item", filters={"prevdoc_docname": doc.name}, fields=["parent"])
            for item in so_items:
                so = frappe.get_doc("Sales Order", item.parent)
                add_doc(extract_doc_data(so))
                if so.web_order_id:
                    web_order_ids.add(so.web_order_id)
        elif getattr(doc, "web_order_id", None):
            web_order_ids.add(doc.web_order_id)

    # Case 2: web_order_id directly
    if filters.get("web_order_id"):
        web_order_ids.add(filters["web_order_id"])

    # Case 3: gather all docs linked to Web Order IDs
    for woid in web_order_ids:
        # Sales Orders
        sales_orders = frappe.get_all("Sales Order", filters={"web_order_id": woid},
                                      fields=["name", "status", "company", "customer", "customer_name", "contact_person", "contact_display",
                                              "transaction_date as posting_date", "total", "currency", "web_order_id", "owner", "creation"])
        for so in sales_orders:
            add_doc(so | {"doctype": "Sales Order"})

            # Quotations linked via SO Items
            quote_links = frappe.get_all("Sales Order Item", filters={"parent": so.name}, fields=["prevdoc_docname"])
            for qr in quote_links:
                if qr.prevdoc_docname:
                    try:
                        quotation = frappe.get_doc("Quotation", qr.prevdoc_docname)
                        add_doc(extract_doc_data(quotation))
                    except frappe.DoesNotExistError:
                        pass

        # Delivery Notes
        dns = frappe.get_all("Delivery Note", filters={"web_order_id": woid},
                             fields=["name", "status", "company", "customer", "customer_name", "contact_person", "contact_display",
                                     "posting_date", "total", "currency", "web_order_id", "owner", "creation"])
        for dn in dns:
            add_doc(dn | {"doctype": "Delivery Note"})

        # Sales Invoices
        sis = frappe.get_all("Sales Invoice", filters={"web_order_id": woid},
                             fields=["name", "status", "company", "customer", "customer_name", "contact_person", "contact_display",
                                     "posting_date", "total", "currency", "web_order_id", "owner", "creation"])
        for si in sis:
            add_doc(si | {"doctype": "Sales Invoice"})

    # Sort results by creation date
    collected_docs.sort(key=lambda d: d.get("creation"))

    # Prepare keys to query comment counts in one batch
    doc_keys = [(d["doctype"], d["name"]) for d in collected_docs]

    # Query all comment counts at once
    if doc_keys:
        # Build WHERE clause with IN tuples
        placeholders = ', '.join(['(%s, %s)'] * len(doc_keys))
        flat_values = [v for tup in doc_keys for v in tup]

        comment_counts = frappe.db.sql(f"""
            SELECT reference_doctype, reference_name, COUNT(*) as count
            FROM `tabComment`
            WHERE comment_type = 'Comment'
            AND (reference_doctype, reference_name) IN ({placeholders})
            GROUP BY reference_doctype, reference_name
        """, flat_values, as_dict=True)

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
    data = get_data(filters)
    return columns, data
