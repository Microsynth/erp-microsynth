# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "microsynth"
app_title = "Microsynth"
app_publisher = "Microsynth, libracore and contributors"
app_description = "Microsynth ERP Applications"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@microsynth.ch"
app_license = "AGPL"

welcome_email_subject = "Activate your new Micosynth ERP account"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/microsynth/css/microsynth.css"
app_include_js = [
    "assets/js/microsynth_templates.min.js",
    "assets/microsynth/js/microsynth_common.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/microsynth/css/microsynth.css"
# web_include_js = "/assets/microsynth/js/microsynth.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Address" :           "public/js/address.js",
    "Contact" :           "public/js/contact.js",
    "Customer" :          "public/js/customer.js",
    "Delivery Note":      "public/js/delivery_note.js",
    "File":               "public/js/file.js",
    "Item Group":         "public/js/item_group.js",
    "Item Price":         "public/js/item_price.js",
    "Item":               "public/js/item.js",
    "Journal Entry":      "public/js/journal_entry.js",
    "Material Request":   "public/js/material_request.js",
    "Payment Entry":      "public/js/payment_entry.js",
    "Payment Reminder":   "public/js/payment_reminder.js",
    "Price List" :        "public/js/price_list.js",
    "Purchase Invoice":   "public/js/purchase_invoice.js",
    "Purchase Order":     "public/js/purchase_order.js",
    "Purchase Receipt":   "public/js/purchase_receipt.js",
    "Quotation":          "public/js/quotation.js",
    "Sales Invoice":      "public/js/sales_invoice.js",
    "Sales Order":        "public/js/sales_order.js",
    "Standing Quotation": "public/js/standing_quotation.js",
    "User":               "public/js/user.js"
}
# include js in doctype lists
doctype_list_js = {
    "Contact" : "public/js/contact_list.js",
    "Customer" : "public/js/customer_list.js",
    "Quotation" : "public/js/quotation_list.js",
    "Delivery Note" : "public/js/delivery_note_list.js",
    "Sales Invoice" : "public/js/sales_invoice_list.js",
    "Sales Order" : "public/js/sales_order_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# extend Jinja environment
jenv = {
    "methods": [
        "get_price_list_rate:microsynth.microsynth.jinja.get_price_list_rate",
        "get_destination_classification:microsynth.microsynth.jinja.get_destination_classification",
        "get_yearly_order_sum:microsynth.microsynth.portfolio.get_yearly_order_sum",
        "get_sales_volume:microsynth.microsynth.portfolio.get_sales_volume",
        "get_sales_qty:microsynth.microsynth.portfolio.get_sales_qty",
        "get_product_type:microsynth.microsynth.portfolio.get_product_type",
        "get_training_records:microsynth.qms.doctype.qm_training_record.qm_training_record.get_training_records",
        "get_qm_reviews:microsynth.qms.doctype.qm_review.qm_review.get_qm_reviews",
        "get_valid_appendices:microsynth.qms.doctype.qm_document.qm_document.get_valid_appendices",
        "get_corrections:microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.get_corrections",
        "get_corrective_actions:microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.get_corrective_actions",
        "get_effectiveness_checks:microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.get_effectiveness_checks",
        "get_qm_changes:microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.get_qm_changes",
        "get_yearly_order_volume:microsynth.microsynth.utils.get_yearly_order_volume",
        "get_html_message:microsynth.microsynth.payment_reminder.get_html_message"
    ]
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "microsynth.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "microsynth.install.before_install"
# after_install = "microsynth.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "microsynth.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }
doc_events = {
    "Contact": {
        "after_insert": "microsynth.microsynth.marketing.lock_contact"
    },
    "Payment Reminder": {
        "after_insert": "microsynth.microsynth.payment_reminder.extend_values",
        "on_submit": "microsynth.microsynth.payment_reminder.transmit_payment_reminder"
    },
    "Quotation": {
        "before_save": "microsynth.microsynth.taxes.set_alternative_tax_template"
    },
    "Sales Order": {
        "before_save": "microsynth.microsynth.taxes.set_alternative_tax_template"
    },
    "Delivery Note": {
        "before_save": "microsynth.microsynth.taxes.set_alternative_tax_template"
    },
    "Sales Invoice": {
        "before_save": "microsynth.microsynth.taxes.set_alternative_tax_template"
    },
    "Communication": {
        "after_insert": "microsynth.microsynth.email_handler.communication_on_insert"
    }

 }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"microsynth.tasks.all"
# 	],
# 	"daily": [
# 		"microsynth.tasks.daily"
# 	],
# 	"hourly": [
# 		"microsynth.tasks.hourly"
# 	],
# 	"weekly": [
# 		"microsynth.tasks.weekly"
# 	]
# 	"monthly": [
# 		"microsynth.tasks.monthly"
# 	]
# }
scheduler_events = {
    "hourly": [
        # Do NOT use the scheduler events. Use a cronjob instead to keep all tasks at the same place.
        
        # "microsynth.microsynth.slims.sync",
        # "microsynth.microsynth.batch_invoice_processing.process_files"
        # "microsynth.microsynth.seqblatt.check_sales_order_completion"
    ],
    "daily": [
        # "microsynth.qms.doctype.qm_document.qm_document.check_update_validity"
    ]
}

# Testing
# -------

# before_tests = "microsynth.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "microsynth.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "microsynth.task.get_dashboard_data"
# }

# hook for migrate cleanup tasks
after_migrate = [
    'microsynth.microsynth.updater.cleanup_languages',
    'microsynth.microsynth.updater.disable_hot_config_in_dev'
]
