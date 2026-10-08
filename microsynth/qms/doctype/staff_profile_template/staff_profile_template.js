// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('Staff Profile Template', {
	refresh: function(frm) {
		set_valid_competency_query(frm);
		if (!frm.doc.disabled) {
			frm.add_custom_button(__('Staff Profile'), function() {
				validate_template_and_open_dialog(frm);
			}, __('Create'));
		}
	}
});

function set_valid_competency_query(frm) {
	const grid = frm.fields_dict.competencies && frm.fields_dict.competencies.grid;
	if (!grid) return;

	const competency_field = grid.get_field('competency');
	if (!competency_field) return;

	competency_field.get_query = function(doc, cdt, cdn) {
		return {
			filters: [
				['Competency', 'status', '=', 'Valid'],
				['Competency', 'docstatus', '=', 1]
			]
		};
	};
}

function validate_template_and_open_dialog(frm) {
	frappe.call({
		'method': 'microsynth.qms.doctype.staff_profile_template.staff_profile_template.validate_template_for_staff_profile',
		'args': {
			'template_name': frm.doc.name
		},
		'callback': function(response) {
			const result = response.message || {};
			if (!result.valid) {
				frappe.msgprint({
					title: __('Invalid Competencies'),
					message: result.message || __('This template has invalid competencies.'),
					indicator: 'red'
				});
				return;
			}

			frappe.prompt(
				[
					{
						fieldname: 'employee',
						fieldtype: 'Link',
						label: __('Employee'),
						options: 'Employee',
						reqd: 1
					}
				],
				function(values) {
					if (!values.employee) {
						frappe.throw(__('Employee is mandatory.'));
					}

					frappe.call({
						'method': 'microsynth.qms.doctype.staff_profile_template.staff_profile_template.create_staff_profile_from_template',
						'args': {
							'template_name': frm.doc.name,
							'employee': values.employee
						},
						'callback': function(create_response) {
							if (create_response.message) {
								frappe.set_route('Form', 'Staff Profile', create_response.message);
							}
						}
					});
				},
				__('Create Staff Profile'),
				__('Create')
			);
		}
	});
}
