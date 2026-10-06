# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from frappe import _


def get_data():
    return {
        'transactions': [
            {
                'label': _('Assignments'),
                'items': ['Staff Profile'],
            }
        ],
    }
