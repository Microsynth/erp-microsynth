// Copyright (c) 2026, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Competency Instruction', {
	refresh: function(frm) {
		const assignment_name = frm.doc.competency_assignment;
		if (!assignment_name) {
			return;
		}

		if (frm.page.wrapper.find('.custom-btn-to-staff-profile').length) {
			return;
		}

		frappe.call({
			method: 'microsynth.qms.doctype.competency_instruction.competency_instruction.get_staff_profile_parent_for_assignment',
			args: { competency_assignment: assignment_name },
			callback: function(response) {
				const parent = response && response.message;
				if (!parent) {
					return;
				}

				const button = frm.add_custom_button(__('To Staff Profile'), function() {
					frappe.set_route('Form', 'Staff Profile', parent);
				});
				button.addClass('btn-primary custom-btn-to-staff-profile');
			}
		});
	}
});
