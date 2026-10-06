// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('Competence', {
	setup: function(frm) {
		frm.fields_dict.qm_documents.grid.get_field('qm_document').get_query = function() {
			return {
				filters: [
					['status', '=', 'Valid']
				]
			};
		};
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Valid") {
			frm.add_custom_button(__('New Version'), function() {
				create_new_version(frm);
			}, __('Create'));
		}
	}
});


function create_new_version(frm) {
	frappe.call({
		'method': 'microsynth.qms.doctype.competence.competence.create_new_version',
		'args': {
			'docname': frm.doc.name
		},
		'callback': function(response) {
			if (response.message && response.message.name) {
				frappe.set_route('Form', 'Competence', response.message.name);
			}
		}
	});
}
