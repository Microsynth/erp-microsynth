from frappe import _


def get_data(data):
    return {
        "fieldname": "item_code",
        "non_standard_fieldnames": {
            "Work Order": "production_item",
            "Product Bundle": "new_item_code",
            "BOM": "item",
            "Batch": "item",
        },
        "transactions": [
            {"label": _("Pricing"), "items": ["Item Price", "Pricing Rule"]},
            {"label": _("Sell"), "items": ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]},
            {
                "label": _("Buy"),
                "items": [
                    "Material Request",
                    "Supplier Quotation",
                    "Request for Quotation",
                    "Purchase Order",
                    "Purchase Receipt",
                    "Purchase Invoice",
                ],
            },
            {"label": _("Traceability"), "items": ["Serial No", "Batch"]},
            {"label": _("Stock Movement"), "items": ["Stock Entry", "Stock Reconciliation"]},
        ],
    }
