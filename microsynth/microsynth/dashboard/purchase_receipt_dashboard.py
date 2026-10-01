from frappe import _


def get_data(data):
    return {
        "fieldname": "purchase_receipt_no",
        "non_standard_fieldnames": {
            "Purchase Invoice": "purchase_receipt",
            "Asset": "purchase_receipt",
            "Landed Cost Voucher": "receipt_document",
            "Auto Repeat": "reference_document",
            "Purchase Receipt": "return_against",
            "Stock Reservation Entry": "from_voucher_no",
            "Quality Inspection": "reference_name",
        },
        "internal_links": {
            "Material Request": ["items", "material_request"],
            "Purchase Order": ["items", "purchase_order"],
            "Project": ["items", "project"],
        },
        "transactions": [
            {"label": _("Related"), "items": ["Purchase Invoice"]},
            {"label": _("Reference"), "items": ["Material Request", "Purchase Order"]},
            {"label": _("Returns"), "items": ["Purchase Receipt"]}
        ],
    }
