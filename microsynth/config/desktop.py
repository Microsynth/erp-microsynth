# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe import _

def get_data():
    return [
        {
            "module_name": "Microsynth",
            "color": "grey",
            "icon": "octicon octicon-file-directory",
            "type": "module",
            "label": _("Microsynth")
        },
        {
            "module_name": "QMS",
            "color": "grey",
            "icon": "octicon octicon-star",
            "type": "module",
            "label": _("QMS")
        }
    ]
