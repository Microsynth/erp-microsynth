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
                       "description": _("REview")
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
