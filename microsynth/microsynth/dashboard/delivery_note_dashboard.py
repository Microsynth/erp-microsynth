from frappe import _


def get_data(data):
    return {
        "fieldname": "delivery_note",
        "non_standard_fieldnames": {
            "Stock Entry": "delivery_note_no",
            "Quality Inspection": "reference_name",
            "Auto Repeat": "reference_document",
            "Purchase Receipt": "inter_company_reference",
        },
        "internal_links": {
            "Sales Order": ["items", "against_sales_order"],
            "Material Request": ["items", "material_request"],
            "Purchase Order": ["items", "purchase_order"],
        },
        "internal_and_external_links": {
            "Sales Invoice": ["items", "against_sales_invoice"],
        },
        "transactions": [
            {"label": _("Reference"), "items": ["Sales Order", "Sales Invoice", "Customs Declaration"]},
            {"label": _("Returns"), "items": ["Stock Entry"]},
            {"label": _("Internal Transfer"), "items": ["Material Request", "Purchase Order", "Purchase Receipt"]}
        ],
    }
