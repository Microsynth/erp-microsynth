// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('Staff Profile', {
	setup: function(frm) {
		frm.fields_dict.competencies.grid.get_field('competency').get_query = function() {
			return {
				filters: {
					status: 'Valid',
					docstatus: 1
				}
			};
		};
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "To Sign") {
			frm.page.clear_primary_action();
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Valid") {
			frm.add_custom_button(__('New Version'), function() {
				create_new_version(frm);
			}, __('Create'));
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "To Sign") {
			show_signing_banner(frm);
			add_sign_button_if_allowed(frm);
		}
	},

	before_submit: function(frm) {
		if (frm.doc.confirm_valid_staff_profile_replacement) {
			delete frm.doc.confirm_valid_staff_profile_replacement;
			return;
		}

		frappe.validated = false;

		return new Promise((resolve, reject) => {
			frappe.call({
				'method': 'microsynth.qms.doctype.staff_profile.staff_profile.has_valid_staff_profile',
				'args': {
					'employee': frm.doc.employee,
					'current_name': frm.doc.name
				},
				'callback': function(response) {
					const has_valid = response.message && response.message.has_valid;
					if (!has_valid) {
						frappe.validated = true;
						resolve();
						return;
					}

					frappe.confirm(
						__('A valid Staff Profile already exists for this employee. If you continue, the previous valid profile will be archived when this one becomes valid. Continue?'),
						function() {
							frm.doc.confirm_valid_staff_profile_replacement = 1;
							frappe.validated = true;
							resolve();
						},
						function() {
							frappe.msgprint(__('Submission cancelled.'));
							reject();
						}
					);
				}
			});
		});
	}
});


function show_signing_banner(frm) {
	let missing_signature = [];

	if (!frm.doc.employee_signed_on || !frm.doc.employee_user || !frm.doc.employee_signature) {
		missing_signature.push(__('Employee'));
	}

	if (!frm.doc.process_owner_signed_on || !frm.doc.process_owner || !frm.doc.process_owner_signature) {
		missing_signature.push(__('Process Owner'));
	}
	console.log('Missing signatures:', missing_signature);
	frm.dashboard.clear_comment();
	if (missing_signature.length > 0) {
		frm.dashboard.add_comment(
			__('<b>Missing signature:</b> ') + missing_signature.join(', '),
			'red',
			true
		);
	}
}


function add_sign_button_if_allowed(frm) {
	frappe.call({
		'method': 'microsynth.qms.doctype.staff_profile.staff_profile.get_signing_users',
		'args': {
			'employee': frm.doc.employee
		},
		'callback': function(response) {
			const data = response.message || {};
			const employee_user = data.employee_user;
			const process_owner = data.process_owner;
			const current_user = frappe.session.user;

			if (current_user === employee_user && !frm.doc.employee_signed_on) {
				frm.page.clear_primary_action();
				frm.page.set_primary_action(__('Sign'), function() {
					sign_staff_profile(frm, 'employee');
				});
				return;
			}

			if (current_user === process_owner && !frm.doc.process_owner_signed_on) {
				frm.page.clear_primary_action();
				frm.page.set_primary_action(__('Sign'), function() {
					sign_staff_profile(frm, 'process_owner');
				});
			}
		}
	});
}


function sign_staff_profile(frm, role) {
	frappe.prompt(
		[
			{ fieldname: 'password', fieldtype: 'Password', label: __('Approval Password'), reqd: 1 }
		],
		function(values) {
			frappe.call({
				'method': 'microsynth.qms.doctype.staff_profile.staff_profile.sign_staff_profile',
				'args': {
					'docname': frm.doc.name,
					'user': frappe.session.user,
					'password': values.password,
					'role': role
				},
				'callback': function(response) {
					if (response.message) {
						frm.reload_doc();
					}
				}
			});
		},
		__('Please enter your approval password'),
		__('Sign')
	);
}


function create_new_version(frm) {
	frappe.call({
		'method': 'microsynth.qms.doctype.staff_profile.staff_profile.create_new_version',
		'args': {
			'docname': frm.doc.name
		},
		'callback': function(response) {
			if (response.message && response.message.name) {
				frappe.set_route('Form', 'Staff Profile', response.message.name);
			}
		}
	});
}
