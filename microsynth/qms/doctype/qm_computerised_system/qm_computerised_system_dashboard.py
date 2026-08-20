from frappe import _


def get_data():
    return {
        'fieldname': 'document_name',
        'non_standard_fieldnames': {
            'QM Change': 'name',
            'QM Nonconformity': 'name'
        },
        'transactions': [
            {
                'label': _("Related Documents"),
                'items': ['QM Log Book', 'QM Change', 'QM Nonconformity'],
            }
        ]
    }


def get_route_options(doc):
    return {
        "document_type": doc.doctype,
        "document_name": doc.name
    }
