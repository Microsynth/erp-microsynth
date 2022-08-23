from __future__ import unicode_literals
from frappe import _

def get_data():
    return[
        {
            "label": _("Sales"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                   {
                       "type": "doctype",
                       "name": "Customer",
                       "label": _("Customer"),
                       "description": _("Customer")                   
                   },
                   {
                       "type": "doctype",
                       "name": "Quotation",
                       "label": _("Quotation"),
                       "description": _("Quotation")                   
                   },
                   {
                       "type": "doctype",
                       "name": "Standing Quotation",
                       "label": _("Standing Quotation"),
                       "description": _("Standing Quotation")                   
                   },
                   {
                       "type": "doctype",
                       "name": "Sales Order",
                       "label": _("Sales Order"),
                       "description": _("Sales Order")                   
                   },
                   {
                       "type": "doctype",
                       "name": "Delivery Note",
                       "label": _("Delivery Note"),
                       "description": _("Delivery Note")                   
                   },
                   {
                       "type": "doctype",
                       "name": "Sales Invoice",
                       "label": _("Sales Invoice"),
                       "description": _("Sales Invoice")                   
                   } 
            ]
        },
        {
            "label": _("Pricing"),
            "icon": "fa fa-money",
            "items": [
                   {
                       "type": "doctype",
                       "name": "Price List",
                       "label": _("Price List"),
                       "description": _("Price List")
                   },
                   {
                        "type": "report",
                        "name": "Pricing Configurator",
                        "label": _("Pricing Configurator"),
                        "doctype": "Price List",
                        "is_query_report": True
                    }
            ]
        },
        {
            "label": _("Master Data"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                   {
                       "type": "doctype",
                       "name": "Item",
                       "label": _("Item"),
                       "description": _("Item")                   
                   },
                   {
                       "type": "doctype",
                       "name": "Oligo",
                       "label": _("Oligo"),
                       "description": _("Oligo")                   
                   },
            ]
        },
        {
            "label": _("Accounting"),
            "icon": "fa fa-money",
            "items": [
                   {
                       "type": "page",
                       "name": "bank_wizard",
                       "label": _("Bank Wizard"),
                       "description": _("Bank Wizard")
                   },
                   {
                       "type": "doctype",
                       "name": "Payment Proposal",
                       "label": _("Payment Proposal"),
                       "description": _("Payment Proposal")
                   },
                   {
                       "type": "doctype",
                       "name": "Payment Reminder",
                       "label": _("Payment Reminder"),
                       "description": _("Payment Reminder")
                   }
            ]
        },
        {
            "label": _("Taxes"),
            "icon": "fa fa-bank",
            "items": [
                   {
                       "type": "doctype",
                       "name": "VAT Declaration",
                       "label": _("VAT Declaration"),
                       "description": _("VAT Declaration")
                   },
                   {
                        "type": "report",
                        "name": "Kontrolle MwSt",
                        "label": _("Kontrolle MwSt"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    }
            ]
        },
        {
            "label": _("Human Resources"),
            "icon": "fa fa-users",
            "items": [
                   {
                       "type": "doctype",
                       "name": "Salary Certificate",
                       "label": _("Salary Certificate"),
                       "description": _("Salary Certificate")
                   },
                   {
                        "type": "report",
                        "name": "Worktime Overview",
                        "label": _("Worktime Overview"),
                        "doctype": "Timesheet",
                        "is_query_report": True
                   },
                   {
                        "type": "report",
                        "name": "Monthly Worktime",
                        "label": _("Monthly Worktime"),
                        "doctype": "Timesheet",
                        "is_query_report": True
                   }
            ]
        },
        {
            "label": _("Settings"),
            "icon": "fa fa-users",
            "items": [
                   {
                       "type": "doctype",
                       "name": "Microsynth Webshop Settings",
                       "label": _("Microsynth Webshop Settings"),
                       "description": _("Microsynth Webshop Settings")
                   },
                   {
                       "type": "doctype",
                       "name": "SLIMS Settings",
                       "label": _("SLIMS Settings"),
                       "description": _("SLIMS Settings")
                   }

            ]
        }
    ]
