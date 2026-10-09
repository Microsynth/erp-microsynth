// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('QM Training Template', {
	setup: function(frm) {
		frm.make_methods = frm.make_methods || {};
		frm.make_methods['QM Training Course'] = function(source_frm) {
			frappe.model.with_doctype('QM Training Course', function() {
				const course = frappe.model.get_new_doc('QM Training Course');
				const excluded_types = ['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button'];
				frappe.get_meta('QM Training Course').fields.forEach(function(field) {
					const source_field = source_frm.meta.fields.find(function(candidate) {
						return candidate.fieldname === field.fieldname;
					});
					if (!source_field || field.fieldname === 'naming_series' || field.no_copy
						|| excluded_types.includes(field.fieldtype)) {
						return;
					}
					const value = source_frm.doc[field.fieldname];
					if (value === undefined) {
						return;
					}
					if (frappe.model.table_fields.includes(field.fieldtype)) {
						if (source_field.options !== field.options) {
							return;
						}
						(value || []).forEach(function(row) {
							const child = frappe.model.add_child(course, field.options, field.fieldname);
							frappe.get_meta(field.options).fields.forEach(function(child_field) {
								if (!child_field.no_copy && !excluded_types.includes(child_field.fieldtype)
									&& row[child_field.fieldname] !== undefined) {
									child[child_field.fieldname] = row[child_field.fieldname];
								}
							});
						});
					} else {
						course[field.fieldname] = value;
					}
				});
				course.training_template = source_frm.doc.name;
				frappe.ui.form.make_quick_entry('QM Training Course', null, null, course);
			});
		};
	}
});
