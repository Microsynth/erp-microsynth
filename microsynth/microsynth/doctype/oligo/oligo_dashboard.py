# -*- coding: utf-8 -*-
# Copyright (c) 2024, libracore AG and contributors
# For license information, please see license.txt

from frappe import _

def get_data():
   return {
      'fieldname': 'oligo',
      'transactions': [
         {
            'label': _("Pre-Sales"),
            'items': ['Quotation']
         },
         {
            'label': _("Sales"),
            'items': ['Sales Order', 'Delivery Note', 'Sales Invoice']
         }
      ]
   }
