# Copyright (c) 2024, libracore AG and contributors
# For license information, please see license.txt

from frappe import _

def get_data():
   return {
      'fieldname': 'document_name',
      'transactions': [
         {
            'label': _("Review"),
            'items': ['QM Review']
         },
         {
            'label': _("Training"),
            'items': ['QM Training']
         }
      ]
   }
