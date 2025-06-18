from __future__ import unicode_literals
from frappe import _

def get_data():
    return [
        {
            "label": _("Sales"),
            "icon": "octicon octicon-file-submodule",
            "items": [
                    {
                       "type": "doctype",
                       "name": "Quotation",
                       "label": _("Quotation"),
                       "description": _("Quotation")
                    },
                    {
                        "type": "report",
                        "name": "Quotation Tracker",
                        "label": _("Quotation Tracker"),
                        "doctype": "Quotation",
                        "is_query_report": True
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
            "label": _("CRM"),
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
                        "type": "page",
                        "name": "contact_merger",
                        "label": _("Contact Merger"),
                        "description": _("Contact Merger")
                    },
                    {
                        "type": "report",
                        "name": "Find Notes",
                        "label": _("Find Notes"),
                        "doctype": "Contact Note",
                        "is_query_report": True
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
                    },
                    {
                        "type": "report",
                        "name": "Oligo envelope sizes",
                        "label": _("Oligo envelope sizes (CH)"),
                        "doctype": "Delivery Note",
                        "is_query_report": True
                    }
            ]
        },
        {
            "label": _("Labels"),
            "icon": "fa fa-tools",
            "items": [
                   {
                        "type": "report",
                        "name": "Label Manager",
                        "label": _("Label Manager"),
                        "doctype": "Sequencing Label",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Label Usage",
                        "label": _("Label Usage"),
                        "doctype": "Sales Order",
                        "is_query_report": True
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
                    },
                    {
                        "type": "report",
                        "name": "Compare Price Lists",
                        "label": _("Compare Price Lists"),
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
                        "name": "Open Sales Orders",
                        "label": _("Open Sales Orders"),
                        "doctype": "Sales Order",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Open Delivery Notes",
                        "label": _("Open Delivery Notes"),
                        "doctype": "Delivery Note",
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
                        "label": _("Tracking Code Registration"),
                        "description": _("Tracking Codes")
                    },
                    {
                        "type": "report",
                        "name": "Missing Tracking Codes",
                        "label": _("Missing Tracking Codes"),
                        "doctype": "Sales Order",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Find Tracking Code",
                        "label": _("Find Tracking Code"),
                        "doctype": "Sales Order",
                        "is_query_report": True
                    },
            ]
        },
        {
            "label": _("Purchasing"),
            "icon": "fa fa-money",
            "items": [
                    {
                        "type": "doctype",
                        "name": "Supplier",
                        "label": _("Supplier"),
                        "description": _("Supplier")
                    },
                    {
                        "type": "report",
                        "name": "Supplier Items",
                        "label": _("Supplier Items"),
                        "doctype": "Item",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Open Material Requests",
                        "label": _("Open Material Requests"),
                        "doctype": "Material Request",
                        "is_query_report": True
                    },
                    {
                        "type": "doctype",
                        "name": "Purchase Order",
                        "label": _("Purchase Order"),
                        "description": _("Purchase Order")
                    },
                    {
                        "type": "doctype",
                        "name": "Purchase Receipt",
                        "label": _("Purchase Receipt"),
                        "description": _("Purchase Receipt")
                    },
                    {
                        "type": "doctype",
                        "name": "Purchase Invoice",
                        "label": _("Purchase Invoice"),
                        "description": _("Purchase Invoice")
                    },
                    {
                        "type": "page",
                        "name": "invoice_entry",
                        "label": _("Invoice Entry"),
                        "description": _("Invoice Entry")
                    },
                    {
                        "type": "page",
                        "name": "approval-manager",
                        "label": _("Approval Manager"),
                        "description": _("Approval Manager")
                    },                    
                    {
                        "type": "doctype",
                        "name": "Payment Proposal",
                        "label": _("Payment Proposal"),
                        "description": _("Payment Proposal")
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
                       "type": "report",
                       "name": "Unallocated Payments",
                       "label": _("Unallocated Payments"),
                       "doctype": _("Payment Entry"),
                       "is_query_report": True
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
                   },
                   {
                       "type": "report",
                       "name": "Reminded Invoices",
                       "label": _("Reminded Invoices"),
                       "doctype": _("Sales Invoice"),
                       "is_query_report": True
                   },
                   {
                       "type": "report",
                       "name": "Accounting Note Overview",
                       "label": _("Accounting Note Overview"),
                       "doctype": _("Accounting Note"),
                       "is_query_report": True
                   },
                   {
                       "type": "report",
                       "name": "Accounts Receivable Microsynth",
                       "label": _("Accounts Receivable Microsynth"),
                       "doctype": "Sales Invoice",
                       "is_query_report": True
                   },
                   {
                       "type": "report",
                       "name": "Customer Accounts Overview",
                       "label": _("Customer Accounts Overview"),
                       "doctype": "Sales Invoice",
                       "is_query_report": True
                   },
                   {
                       "type": "report",
                       "name": "Avis Control",
                       "label": _("Avis Control"),
                       "doctype": "Payment Entry",
                       "is_query_report": True
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
                   },
                   {
                       "type": "doctype",
                       "name": "Accounts Settings",
                       "label": _("Accounts Settings"),
                       "description": _("Accounts Settings")
                   },
                   {
                       "type": "doctype",
                       "name": "Batch Invoice Processing Settings",
                       "label": _("Batch Invoice Processing Settings"),
                       "description": _("Batch Invoice Processing Settings")
                   },
                   {
                        "type": "report",
                        "name": "Item Accounting",
                        "label": _("Item Accounting"),
                        "doctype": "Item",
                        "is_query_report": True
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
                        "name": "Payment Allocation",
                        "label": _("Payment Allocation"),
                        "description": _("Payment Allocation"),
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
                       "type": "doctype",
                       "name": "Abacus Export File",
                       "label": _("Abacus Export"),
                       "description": _("Abacus Export")
                    },
                    {
                       "type": "doctype",
                       "name": "Abacus Export File Addition",
                       "label": _("Abacus Export Addition"),
                       "description": _("Abacus Export Addition")
                    }
            ]
        },
        {
            "label": _("Reporting"),
            "icon": "fa fa-users",
            "items": [
                    {
                        "type": "report",
                        "name": "Sales Overview",
                        "label": _("Sales Overview"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Revenue Export",
                        "label": _("Revenue Export (Pivot)"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Sales Analytics",
                        "label": _("Sales Analytics"),
                        "doctype": "Sales Order",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Invoice Summary",
                        "label": _("Invoice Summary"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Commission Calculator",
                        "label": _("Commission Calculator"),
                        "doctype": "Sales Invoice",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Label Accounting",
                        "label": _("Label Accounting"),
                        "doctype": "Sales Order",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Shipping Times",
                        "label": _("Shipping Times"),
                        "doctype": "Tracking Code",
                        "is_query_report": True
                    }
            ]
        },
                {
            "label": _("Product Management"),
            "icon": "fa fa-users",
            "items": [
                    {
                        "type": "report",
                        "name": "Benchmarking Information",
                        "label": _("Benchmarking Information"),
                        "doctype": "Benchmark",
                        "is_query_report": True
                    },
                    {
                        "type": "report",
                        "name": "Product Ideas",
                        "label": _("Product Ideas"),
                        "doctype": "Product Idea",
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
        }
    ]
