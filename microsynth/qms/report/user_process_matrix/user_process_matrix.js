// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["User Process Matrix"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company"
		},
		{
			"fieldname": "user",
			"label": __("User"),
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname": "qm_process",
			"label": __("QM Process"),
			"fieldtype": "Link",
			"options": "QM Process"
		},
		{
			"fieldname": "is_process_owner",
			"label": __("Is Process Owner"),
			"fieldtype": "Select",
			"options": "\nYes\nNo"
		}
	],
	"onload": (report) => {
		report.page.add_inner_button(__("Print Process Assignment Overview"), function () {
			const company = report.get_filter_value("company");

			if (!company) {
				frappe.msgprint(__("Please set the Company filter before printing the process assignment overview."));
				return;
			}

			frappe.call({
				method: "microsynth.qms.report.user_process_matrix.user_process_matrix.create_organigram_pdf",
				args: {
					company: company,
					user: report.get_filter_value("user"),
					qm_process: report.get_filter_value("qm_process"),
					is_process_owner: report.get_filter_value("is_process_owner")
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
