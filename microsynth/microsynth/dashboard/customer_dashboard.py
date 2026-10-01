from frappe import _


def get_data(data):
    return {
        "fieldname": "customer",
        "non_standard_fieldnames": {
            "Payment Entry": "party",
            "Quotation": "party_name",
            "Opportunity": "party_name",
            "Bank Account": "party",
            "Subscription": "party",
        },
        "dynamic_links": {"party_name": ["Customer", "quotation_to"]},
        "transactions": [
            {"label": _("Pre Sales"), "items": ["Quotation", "Standing Quotation"]},
            {"label": _("Orders"), "items": ["Sales Order", "Delivery Note", "Sales Invoice"]},
            {"label": _("Quality Management"), "items": ["QM Document"]},
            {"label": _("Payments"), "items": ["Payment Entry"]},
            #{"label": _("Support"), "items": ["Issue", "Maintenance Visit", "Installation Note", "Warranty Claim"]},
        ]
    }
