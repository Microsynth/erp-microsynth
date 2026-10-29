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
			// Open the clicked assignment, not every assignment sharing this cell.
			const assignment_names = cell.assignment_name ? [cell.assignment_name] : [];
			const assignment_names_attr = frappe.utils.escape_html(JSON.stringify(assignment_names)).replace(/"/g, "&quot;");
			const background = colors[cell.status] || colors["Not Assigned"];
			const title = frappe.utils.escape_html(
				column.employee_name + " (" + column.employee + "): " + __(cell.status)
			).replace(/"/g, "&quot;");
			return '<span class="competency-cell" data-assignment-names="' + assignment_names_attr + '" data-competency="' + frappe.utils.escape_html(data.competency || "").replace(/"/g, "&quot;") + '" data-employee="' + frappe.utils.escape_html(column.employee || "").replace(/"/g, "&quot;") + '" title="' + title + '" style="display: block; text-align: center; '
				+ 'background-color: ' + background + '; color: #212529; padding: 2px 4px; '
				+ 'border-radius: 3px;">' + frappe.utils.escape_html(cell.label) + '</span>';
		}).join("");
	},
	"onload": function(report) {
		hide_chart_buttons();
		report.page.wrapper.off("dblclick", ".competency-cell");
		report.page.wrapper.on("dblclick", ".competency-cell", function (event) {
			const element = event.currentTarget;
			let assignment_names = [];
			try {
				assignment_names = JSON.parse(element.getAttribute("data-assignment-names") || "[]");
			} catch (err) {
				assignment_names = (element.getAttribute("data-assignment-names") || "")
					.split(",")
					.map(function (name) { return name.trim(); })
					.filter(Boolean);
			}
			if (!assignment_names.length) {
				return;
			}
			frappe.call({
				method: "microsynth.qms.report.competency_matrix.competency_matrix.get_cell_details",
				args: { assignment_names: assignment_names },
				freeze: true,
				freeze_message: __("Loading competency details..."),
				callback: function (response) {
					if (!response || !response.message) {
						return;
					}
					frappe.msgprint({
						title: response.message.title || __("Competency Details"),
						message: response.message.html || response.message,
						indicator: "blue",
					});
				}
			});
		});

		const legend = [
			'<div style="margin: 10px 0 0; padding: 8px 12px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; color: #212529; background: transparent; border: none;">',
			'<strong>' + __('Legend') + ':</strong>',
			'<span><strong>M</strong> = ' + __('Main responsibility') + '</span>',
			'<span><strong>S</strong> = ' + __('Substitute responsibility') + '</span>',
			'<span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:#d4edda;border:1px solid #c3e6cb;vertical-align:middle;margin-right:6px;"></span>' + __('Achieved') + '</span>',
			'<span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:#fff3cd;border:1px solid #ffeeba;vertical-align:middle;margin-right:6px;"></span>' + __('Planned') + '</span>',
			'<span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:#f8d7da;border:1px solid #f5c6cb;vertical-align:middle;margin-right:6px;"></span>' + __('Not assigned') + '</span>',
			'<span class="text-muted">' + __('Double-click an Achieved or Planned cell to see details.') + '</span>',
			'</div>'
		].join("");

		report.page.wrapper.find(".page-content").prepend(legend);
	}
};
