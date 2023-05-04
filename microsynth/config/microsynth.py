from __future__ import unicode_literals
from frappe import _

def get_data():
    return[
        {
            "label": _("Sales"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                    {
                        "type": "report",
                        "name": "Customer Finder",
                        "label": _("Customer Finder"),
                        "doctype": "Contact",
                        "is_query_report": True
                    },
                    {
                       "type": "doctype",
                       "name": "Customer",
                       "label": _("Customer"),
                       "description": _("Customer")
                    },
                    {
                       "type": "doctype",
                       "name": "Contact",
                       "label": _("Contact"),
                       "description": _("Contact")
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
            "label": _("Oligo"),
            "icon": "fa fa-tools",
            "items": [
                   {
                        "type": "report",
                        "name": "Oligo Orders Export",
                        "label": _("Oligo Orders Export"),
                        "doctype": "Sales Order",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Oligo Orders Ready To Package",
                        "label": _("Oligo Orders Ready To Package (CH)"),
                        "doctype": "Delivery Note",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Oligo Orders Export Ready To Package",
                        "label": _("Oligo Orders Export Ready To Package (not CH)"),
                        "doctype": "Delivery Note",
                        "is_query_report": True
                    }
            ]
        },
        {
            "label": _("Sequencing"),
            "icon": "fa fa-tools",
            "items": [
                   {
                       "type": "doctype",
                       "name": "Sequencing Label",
                       "label": _("Sequencing Label"),
                       "description": _("Sequencing Label")
                   },
                   {
                        "type": "report",
                        "name": "Open Label Orders",
                        "label": _("Open Label Orders"),
                        "doctype": "Sales Order",
                        "is_query_report": True
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
            "label": _("Administration"),
            "icon": "fa fa-money",
            "items": [
                    {
                       "type": "doctype",
                       "name": "Customs Declaration",
                       "label": _("Customs Declaration"),
                       "description": _("Customs Declaration")
                    },
                    {
                       "type": "report",
                       "name": "Orders on Hold",
                       "label": _("Orders on Hold"),
                       "doctype": "Sales Order",
                       "is_query_report": True
                    },
                    {
                       "type": "report",
                       "name": "Customer Credits",
                       "label": _("Customer Credits"),
                       "doctype": "Sales Invoice",
                       "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Invoiceable Services",
                        "label": _("Invoiceable Services"),
                        "doctype": "Delivery Note",
                        "is_query_report": True
                    },
                    {
                        "type": "page",
                        "name": "tracking_codes",
                        "label": _("Tracking Codes"),
                        "description": _("Tracking Codes")
                    }
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
                       "name": "Microsynth Settings",
                       "label": _("Microsynth Settings"),
                       "description": _("Microsynth Settings")
                   },
                   {
                       "type": "doctype",
                       "name": "SLIMS Settings",
                       "label": _("SLIMS Settings"),
                       "description": _("SLIMS Settings")
                   },
                   {
                       "type": "doctype",
                       "name": "Label Range",
                       "label": _("Label Range"),
                       "description": _("Label Range")
                   },
                   {
                       "type": "doctype",
                       "name": "Flushbox Settings",
                       "label": _("Flushbox Settings"),
                       "description": _("Flushbox Settings")
                   },
                   {
                       "type": "doctype",
                       "name": "Tax Matrix",
                       "label": _("Tax Matrix"),
                       "description": _("Tax Matrix")
                   }
            ]
        },
        {
            "label": _("Export"),
            "icon": "fa fa-users",
            "items": [
                    {
                        "type": "report",
                        "name": "DATEV Export",
                        "label": _("DATEV Export"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Fiscal Representation Export",
                        "label": _("Fiscal Representation Export"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Customer Payments",
                        "label": _("Customer Payments"),
                        "doctype": "GL Entry",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "doctype": "GL Entry",
                        "name": "Intrastat",
                        "label": _("Intrastat"),
                        "description": _("Intrastat"),
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Accounts Receivable Microsynth",
                        "label": _("Accounts Receivable Microsynth"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    }
            ]
        }
    ]
