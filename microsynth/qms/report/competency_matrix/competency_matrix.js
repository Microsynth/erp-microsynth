// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Competency Matrix"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company"
		},
		{
			"fieldname": "department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"get_query": function () {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: company ? { company: company } : {} };
			}
		},
		{
			"fieldname": "competency_scope",
			"label": __("Competency Scope"),
			"fieldtype": "Link",
			"options": "Competency Scope"
		}
	],
	"formatter": function (value, row, column, data, default_formatter) {
		if (!column.employee || !data) {
			return default_formatter(value, row, column, data);
		}

		const assignments = (data._assignments || {})[column.fieldname] || [];
		const cells = assignments.length ? assignments : [{ label: "-", status: "Not Assigned" }];
		const colors = {
			"Achieved": "#d4edda",
			"Planned": "#fff3cd",
			"Not Assigned": "#f8d7da"
		};
		return cells.map(function (cell) {
			const background = colors[cell.status] || colors["Not Assigned"];
			const title = frappe.utils.escape_html(
				column.employee_name + " (" + column.employee + "): " + __(cell.status)
			).replace(/"/g, "&quot;");
			return '<span title="' + title + '" style="display: block; text-align: center; '
				+ 'background-color: ' + background + '; color: #212529; padding: 2px 4px; '
				+ 'border-radius: 3px;">' + frappe.utils.escape_html(cell.label) + '</span>';
		}).join("");
	},
	"onload": function(report) {
		hide_chart_buttons();
	}
};
