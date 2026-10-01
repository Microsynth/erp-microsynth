from frappe import _


def get_data(data):
    return {
        "fieldname": "sales_order",
        "non_standard_fieldnames": {
            "Delivery Note": "against_sales_order",
            "Journal Entry": "reference_name",
            "Payment Entry": "reference_name",
            "Payment Request": "reference_name",
            "Auto Repeat": "reference_document",
            "Maintenance Visit": "prevdoc_docname",
            "Stock Reservation Entry": "voucher_no",
        },
        "internal_links": {
            "Quotation": ["items", "prevdoc_docname"],
            "BOM": ["items", "bom_no"],
            "Blanket Order": ["items", "blanket_order"],
            "Purchase Order": ["items", "purchase_order"],
        },
        "transactions": [
            {"label": _("Fulfillment"), "items": ["Sales Invoice", "Delivery Note", "Tracking Code"]},
            #{"label": _("Purchasing"), "items": ["Material Request", "Purchase Order"]},
            {"label": _("Reference"), "items": ["Quotation"]},
            {"label": _("Payment"), "items": ["Payment Entry", "Journal Entry"]},
        ]
    }
