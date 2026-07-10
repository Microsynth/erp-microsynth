// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('QM Computerised System', {
	refresh: function(frm) {
		const company = frm.doc.company;

		// remove Menu > Duplicate and Menu > New QM Computerised System
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();
        var new_target ="span[data-label='" + __("New QM Computerised System") + "']";
        $(new_target).parent().parent().remove();

        frm.dashboard.clear_comment();

        if (frm.doc.qm_process && company) {
            frappe.call({
                'method': "microsynth.qms.doctype.qm_computerised_system.qm_computerised_system.get_qm_process_owner",
                'args': {
                    'qm_process': frm.doc.qm_process,
                    'company': company
                },
                'callback': function(r) {
                    const isProcessOwner = (r.message || []).includes(frappe.session.user);
                    if (isProcessOwner) {
                        // apply_field_permissions(frm, true);
                        add_custom_buttons(frm, true);
                    } else {
                        // apply_field_permissions(frm, false);
                        add_custom_buttons(frm, false);
                    }
                }
            });
        } else {
			// apply_field_permissions(frm, false);
            add_custom_buttons(frm, false);
        }
	}
});


function get_allowed_transitions(frm, isProcessOwner) {
    const status = frm.doc.status;
    const roles = frappe.user_roles;
    const user = frappe.session.user;

    const is_qau = roles.includes('QAU');
    const is_responsible_user = frm.doc.responsible_user === user;
    const is_owner_or_responsible_user = isProcessOwner || is_responsible_user;
    const is_gmp = frm.doc.regulatory_classification === 'GMP';

    const rules = [
        {
            condition: () => is_qau,
            transitions: [
                ['Unapproved', 'Validated'],
                ['Validated', 'Decommissioned'],
                ['Decommissioned', 'Validated'],
                ['Validated', 'Unapproved']
            ]
        },
        {
            condition: () => is_owner_or_responsible_user && !is_gmp,
            transitions: [
                ['Unapproved', 'Validated'],
                ['Validated', 'Decommissioned'],
                ['Validated', 'Unapproved']
            ]
        }
    ];

    const transitions = new Set();
    rules.forEach(rule => {
        if (rule.condition()) {
            rule.transitions.forEach(([from, to]) => {
                transitions.add(`${from}|${to}`);
            });
        }
    });

    return Array.from(transitions)
        .map(t => t.split('|'))
        .filter(([from]) => from === status);
}


function add_custom_buttons(frm, isProcessOwner) {
    frm.clear_custom_buttons();

    const transitions = get_allowed_transitions(frm, isProcessOwner);
    const labels = {
        'Unapproved|Validated': 'Validate',
        'Validated|Decommissioned': 'Decommission',
        'Decommissioned|Validated': 'Validate',
        'Validated|Unapproved': 'Set Unapproved'
    };

    transitions.forEach(([from, to]) => {
        const label = labels[`${from}|${to}`] || to;
        const color = (to === 'Validated') ? 'btn-success' : 'btn-danger';

        frm.add_custom_button(__(label), function() {
            frm.set_value('status', to);
            frm.save()
        }).addClass(color);
    });

    if (!frm.doc.__islocal) {
        frm.add_custom_button(__('Log Book Entry'), function() {
            frappe.new_doc('QM Log Book', {
                document_type: frm.doc.doctype,
                document_name: frm.doc.name
            });
        }, __('Create'));
    }
}
