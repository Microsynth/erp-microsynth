// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Employee Entries and Exits"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("company") || frappe.defaults.get_global_default("company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 0
		}
	],
	"onload": (report) => {
		report.page.add_inner_button(__("Print Overview"), function () {
			const company = report.get_filter_value("company");
			const from_date = report.get_filter_value("from_date");
			const to_date = report.get_filter_value("to_date");

			if (!company || !from_date) {
				frappe.msgprint(__("Please set Company and From Date before printing."));
				return;
			}

			frappe.call({
				method: "microsynth.microsynth.report.employee_entries_and_exits.employee_entries_and_exits.create_print_overview_pdf",
				args: {
					company: company,
					from_date: from_date,
					to_date: to_date
				},
				freeze: true,
				freeze_message: __("Creating PDF ..."),
				callback: function (response) {
					if (response && response.message) {
						window.open(response.message, "_blank");
					}
				}
			});
		});

		hide_chart_buttons();
	}
};
