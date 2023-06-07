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

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/microsynth/css/microsynth.css"
app_include_js = [
	"/assets/microsynth/js/microsynth_common.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/microsynth/css/microsynth.css"
# web_include_js = "/assets/microsynth/js/microsynth.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Customer" : "public/js/customer.js",
    "Contact" : "public/js/contact.js",
    "Price List" : "public/js/price_list.js",
    "Quotation": "public/js/quotation.js",
    "Sales Order": "public/js/sales_order.js",
    "Delivery Note": "public/js/delivery_note.js",
    "Sales Invoice": "public/js/sales_invoice.js",
    "Payment Entry": "public/js/payment_entry.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# extend Jinja environment
jenv = {
    "methods": [
        "get_price_list_rate:microsynth.microsynth.jinja.get_price_list_rate",
        "get_destination_classification:microsynth.microsynth.jinja.get_destination_classification",
        "get_sales_volume:microsynth.microsynth.sales_overview.get_sales_volume",
        "get_sales_qty:microsynth.microsynth.sales_overview.get_sales_qty",
        "get_product_type:microsynth.microsynth.sales_overview.get_product_type"
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
    "Payment Reminder": {
        "after_insert": "microsynth.microsynth.payment_reminder.extend_values"
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
        "microsynth.microsynth.slims.sync",
        # "microsynth.microsynth.seqblatt.check_sales_order_completion"
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
