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
                        "type": "report",
                        "name": "Releasable Documents",
                        "label": _("Releasable Documents"),
                        "doctype": "QM Document",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Training Confirmations",
                        "label": _("Training Confirmations"),
                        "doctype": "QM Training Record",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Revision Required",
                        "label": _("Revision Required"),
                        "doctype": "QM Document",
                        "is_query_report": True
                    },
                    {
                       "type": "doctype",
                       "name": "QM Review",
                       "label": _("Review"),
                       "description": _("Review")
                    },
                    {
                       "type": "doctype",
                       "name": "QM Revision",
                       "label": _("Revision"),
                       "description": _("Revision")
                    }
            ]
        },
        {
            "label": _("Training Courses"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                    {
                       "type": "doctype",
                       "name": "QM Training Course",
                       "label": _("Training Course"),
                       "description": _("Training Course")
                    }
            ]
        },
        {
            "label": _("Nonconformities"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                    {
                       "type": "doctype",
                       "name": "QM Nonconformity",
                       "label": _("Nonconformity"),
                       "description": _("QM Nonconformity")
                    },
                    {
                        "type": "report",
                        "name": "Pending Nonconformities",
                        "label": _("Pending Nonconformities"),
                        "doctype": "QM Nonconformity",
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
        },
        {
            "label": _("Settings"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                {
                   "type": "doctype",
                   "name": "Signature",
                   "label": _("Signature"),
                   "description": _("Signature")
                },
                {
                   "type": "doctype",
                   "name": "User Settings",
                   "label": _("User Settings"),
                   "description": _("User Settings")
                },
                {
                   "type": "doctype",
                   "name": "QM Process",
                   "label": _("QM Process"),
                   "description": _("QM Process")
                }
            ]
        }
    ]
