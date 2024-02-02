from __future__ import unicode_literals
from frappe import _

def get_data():
    return [
        {
            "label": _("Document Management"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                    {
                       "type": "doctype",
                       "name": "QM Document",
                       "label": _("Document"),
                       "description": _("Document")
                    },
                    {
                       "type": "doctype",
                       "name": "QM Review",
                       "label": _("Review"),
                       "description": _("Review")
                    },
                    {
                       "type": "doctype",
                       "name": "QM Training Record",
                       "label": _("Training Record"),
                       "description": _("Training Record")
                    },
                    {
                        "type": "report",
                        "name": "Training Confirmations",
                        "label": _("Training Confirmations"),
                        "doctype": "QM Training Record",
                        "is_query_report": True
                    }
            ]
        },
        {
            "label": _("Complaints"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                    {
                       "type": "doctype",
                       "name": "Contact Note",
                       "label": _("Contact Notes"),
                       "description": _("Contact Note")
                    }
            ]
        }
    ]
