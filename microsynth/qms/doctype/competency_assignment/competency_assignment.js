// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('Competency Assignment', {
	competency: function(frm, cdt, cdn) {
		update_instruction_button_state(frm, cdt, cdn);
	},

	instruction: function(frm) {
		frappe.msgprint(__('Instruction confirmation is not implemented yet.'));
	}
});


function update_instruction_button_state(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) {
		return;
	}

	if (!row.competency) {
		row.requires_on_the_job_instruction = 0;
		frm.fields_dict.competencies.grid.refresh();
		return;
	}

	frappe.call({
		method: 'microsynth.qms.doctype.competency.competency.get_on_the_job_instruction_requirements',
		args: {
			competency_names: [row.competency]
		},
		callback: function(response) {
			const requirements = response.message || {};
			row.requires_on_the_job_instruction = requirements[row.competency] ? 1 : 0;
			frm.fields_dict.competencies.grid.refresh();
		}
	});
}
