import frappe
from frappe import _

def get_data(data):
    return {
        "fieldname": "contact_person",
        "non_standard_fieldnames": {
            "Standing Quotation": "contact",
        },

        "transactions": [
            {"label": _("Pre Sales"), "items": ["Quotation", "Standing Quotation", "Credit Account"]},
            {"label": _("Orders"), "items": ["Sales Order", "Delivery Note", "Sales Invoice"]},
            {"label": _("Marketing"), "items": ["Contact Note", "Benchmark", "Product Idea"]}
        ]
    }
