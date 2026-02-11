# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def get_columns():
    return [
        {"label": "DocType", "fieldname": "doctype", "fieldtype": "Data", "width": 120},
        {"label": "Document ID", "fieldname": "name", "fieldtype": "Dynamic Link", "options": "doctype", "width": 100},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 75, "align": "left"},
        {"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 250, "align": "left"},
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 75},
        {"label": "Comments", "fieldname": "comments", "fieldtype": "Int", "width": 80},
        {"label": "Creator", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 200},
        {"label": "Creation Date", "fieldname": "creation", "fieldtype": "Date", "width": 125},
    ]


def extract_doc_data(doc):
    """
    Uniform representation of all purchase docs.
    """
    if doc.doctype == "Item Request" and doc.rate is not None and doc.qty:
        doc.grand_total = doc.rate * doc.qty
    if doc.doctype == "Material Request":
        # get Supplier info from first Material Request Item if available
        mr_item = doc.items[0] if doc.items else None
        if mr_item and mr_item.supplier:
            doc.supplier = mr_item.supplier
        if mr_item and mr_item.supplier_name:
            doc.supplier_name = mr_item.supplier_name
        if mr_item and mr_item.item_request_currency:
            doc.currency = mr_item.item_request_currency
        if mr_item and mr_item.rate is not None and mr_item.qty:
            doc.grand_total = mr_item.rate * mr_item.qty
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "status": doc.get("status"),
        "company": doc.get("company"),

        # supplier fields
        "supplier": doc.get("supplier"),
        "supplier_name": doc.get("supplier_name"),

        "posting_date": doc.get("transaction_date") or doc.get("posting_date") or doc.get("creation"),
        "grand_total": doc.get("grand_total"),
        "currency": doc.get("currency"),
        "creation": doc.get("creation"),
        "owner": doc.get("owner"),
    }


def get_data(filters):
    if not filters.get("document_id"):
        return []

    collected = []
    seen = set()  # (doctype, name)

    def add(doc_dict):
        if doc_dict not in collected:
            collected.append(doc_dict)

    def safe_fetch(doctype, name):
        key = (doctype, name)
        if key in seen:
            return
        try:
            doc = frappe.get_doc(doctype, name)
            traverse(doc)
        except frappe.DoesNotExistError:
            pass

    def traverse(doc):
        key = (doc.doctype, doc.name)
        if key in seen:
            return

        seen.add(key)
        add(extract_doc_data(doc))

        handler = handlers.get(doc.doctype)
        if handler:
            handler(doc)


    # Handlers for traversal

    def handle_item_request(doc):
        # IR → MR
        if doc.material_request:
            safe_fetch("Material Request", doc.material_request)


    def handle_material_request(doc):
        # MR → PO
        po_items = frappe.get_all(
            "Purchase Order Item",
            filters={"material_request": doc.name},
            fields=["parent"]
        )
        for row in po_items:
            safe_fetch("Purchase Order", row.parent)

        # MR → IR (reverse lookup)
        ir_list = frappe.get_all(
            "Item Request",
            filters={"material_request": doc.name},
            fields=["name"]
        )
        for row in ir_list:
            safe_fetch("Item Request", row.name)


    def handle_purchase_order(doc):
        """
        Traverse from Purchase Order → Material Request / Supplier Quotation / Purchase Receipt / Purchase Invoice
        """
        # PO → Material Request
        mr_items = frappe.get_all(
            "Purchase Order Item",
            filters={"parent": doc.name},
            fields=["material_request"]
        )
        for item in mr_items:
            if item.material_request:
                safe_fetch("Material Request", item.material_request)

        # PO → Supplier Quotation
        sq_items = frappe.get_all(
            "Purchase Order Item",
            filters={"parent": doc.name},
            fields=["supplier_quotation"]
        )
        for item in sq_items:
            if item.supplier_quotation:
                safe_fetch("Supplier Quotation", item.supplier_quotation)

        # PO → Purchase Receipt
        pr_items = frappe.get_all(
            "Purchase Receipt Item",
            filters={"purchase_order": doc.name},
            fields=["parent"]
        )
        for item in pr_items:
            safe_fetch("Purchase Receipt", item.parent)

        # PO → Purchase Invoice
        pi_items = frappe.get_all(
            "Purchase Invoice Item",
            filters={"purchase_order": doc.name},
            fields=["parent"]
        )
        for item in pi_items:
            safe_fetch("Purchase Invoice", item.parent)


    def handle_purchase_receipt(doc):
        """PR → PO + PI"""
        pr_items = frappe.get_all(
            "Purchase Receipt Item",
            filters={"parent": doc.name},
            fields=["purchase_order"]
        )
        for row in pr_items:
            if row.purchase_order:
                safe_fetch("Purchase Order", row.purchase_order)

        # PR → PI
        pi_items = frappe.get_all(
            "Purchase Invoice Item",
            filters={"purchase_receipt": doc.name},
            fields=["parent"]
        )
        for row in pi_items:
            safe_fetch("Purchase Invoice", row.parent)


    def handle_purchase_invoice(doc):
        """PI → PO + PR"""
        pi_items = frappe.get_all(
            "Purchase Invoice Item",
            filters={"parent": doc.name},
            fields=["purchase_order", "purchase_receipt"]
        )
        for row in pi_items:
            if row.purchase_order:
                safe_fetch("Purchase Order", row.purchase_order)
            if row.purchase_receipt:
                safe_fetch("Purchase Receipt", row.purchase_receipt)


    def handle_supplier_quotation(doc):
        """SQ → PO"""
        po_items = frappe.get_all(
            "Purchase Order Item",
            filters={"supplier_quotation": doc.name},
            fields=["parent"]
        )
        for row in po_items:
            safe_fetch("Purchase Order", row.parent)


    # Master handler map
    handlers = {
        "Item Request": handle_item_request,
        "Material Request": handle_material_request,
        "Purchase Order": handle_purchase_order,
        "Purchase Receipt": handle_purchase_receipt,
        "Purchase Invoice": handle_purchase_invoice,
        "Supplier Quotation": handle_supplier_quotation
    }
    # Starting Point: Document ID
    prefix = filters["document_id"].split("-")[0]

    prefix_map = {
        "IR": "Item Request",
        "MR": "Material Request",
        "PQTN": "Supplier Quotation",
        "PO": "Purchase Order",
        "PR": "Purchase Receipt",
        "PI": "Purchase Invoice"
    }

    doctype = prefix_map.get(prefix)
    if not doctype:
        frappe.throw("Invalid Document ID prefix. Must start with IR-, MR-, PO-, PR-, PI- or PQTN-.")

    safe_fetch(doctype, filters["document_id"])

    # Sort by creation
    collected.sort(key=lambda d: d.get("creation") or "")

    # Count comments
    keys = [(d["doctype"], d["name"]) for d in collected]

    if keys:
        placeholders = ", ".join(["(%s, %s)"] * len(keys))
        values = [x for tup in keys for x in tup]

        comment_rows = frappe.db.sql(f"""
            SELECT reference_doctype, reference_name, COUNT(*) AS count
            FROM `tabComment`
            WHERE comment_type='Comment'
            AND (reference_doctype, reference_name) IN ({placeholders})
            GROUP BY reference_doctype, reference_name
        """, values, as_dict=True)

        comment_map = {(r.reference_doctype, r.reference_name): r.count for r in comment_rows}
    else:
        comment_map = {}

    # Attach comment count
    for d in collected:
        d["comments"] = comment_map.get((d["doctype"], d["name"]), 0)

    return collected


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)
