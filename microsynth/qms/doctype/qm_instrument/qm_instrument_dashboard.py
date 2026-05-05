
from frappe import _


def get_data():
    return {
        'fieldname': 'document_name',
        'transactions': [
            {
                'label': _("Log Book Entries"),
                'items': ['QM Log Book'],
            }
        ]
    }


def get_route_options(doc):
    return {
        "document_type": doc.doctype,
        "document_name": doc.name
    }
