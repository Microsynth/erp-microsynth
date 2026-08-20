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
                        apply_field_permissions(frm, true);
                        add_custom_buttons(frm, true);
                    } else {
                        apply_field_permissions(frm, false);
                        add_custom_buttons(frm, false);
                    }
                }
            });
        } else {
			apply_field_permissions(frm, false);
            add_custom_buttons(frm, false);
        }

        ensure_dashboard_reference_entries(frm);
        hide_selected_dashboard_add_buttons(frm);
        update_dashboard_reference_links(frm);
	}
});


function ensure_dashboard_reference_entries(frm) {
    const hasChange = !!find_dashboard_link(frm, 'QM Change').length;
    const hasNonconformity = !!find_dashboard_link(frm, 'QM Nonconformity').length;

    if (!hasChange || !hasNonconformity) {
        frm.dashboard.add_transactions([
            {
                label: __('Related Documents'),
                items: ['QM Change', 'QM Nonconformity']
            }
        ]);
    }
}


function hide_selected_dashboard_add_buttons(frm) {
    ['QM Log Book', 'QM Change', 'QM Nonconformity'].forEach(function(doctype) {
        const $link = find_dashboard_link(frm, doctype);
        if (!$link.length) {
            return;
        }

        $link.closest('.document-link').find('.btn-new').css('visibility', 'hidden');
    });
}


function find_dashboard_link(frm, doctype) {
    let $link = frm.dashboard.transactions_area.find(`a[data-doctype="${doctype}"]`).first();
    if ($link.length) {
        return $link;
    }

    return frm.dashboard.transactions_area.find('a').filter(function() {
        return ($(this).text() || '').trim().startsWith(doctype);
    }).first();
}


function set_dashboard_count($link, count) {
    if (!$link || !$link.length) {
        return;
    }

    $link.find('.qmcs-linked-count').remove();
    $link.append(' <span class="qmcs-linked-count text-muted">&nbsp;&nbsp;' + count + '</span>');
}


function set_dashboard_route_handler($link, doctype, names) {
    if (!$link || !$link.length) {
        return;
    }

    $link.off('click.qmcs').on('click.qmcs', function(e) {
        e.preventDefault();
        if (names && names.length) {
            frappe.set_route('List', doctype, {
                name: ['in', names]
            });
            return;
        }

        frappe.set_route('List', doctype, {
            name: ['in', ['__no_linked_records__']]
        });
    });
}


function update_dashboard_reference_links(frm) {
    if (frm.doc.__islocal || !frm.doc.name) {
        return;
    }

    frappe.call({
        method: 'microsynth.qms.doctype.qm_computerised_system.qm_computerised_system.get_linked_qm_documents',
        args: {
            qm_computerised_system: frm.doc.name
        },
        callback: function(r) {
            const data = r.message || {};
            const changeNames = data.qm_change_names || [];
            const nonconformityNames = data.qm_nonconformity_names || [];

            const $changeLink = find_dashboard_link(frm, 'QM Change');
            set_dashboard_count($changeLink, data.qm_change_count || 0);
            set_dashboard_route_handler($changeLink, 'QM Change', changeNames);

            const $nonconformityLink = find_dashboard_link(frm, 'QM Nonconformity');
            set_dashboard_count($nonconformityLink, data.qm_nonconformity_count || 0);
            set_dashboard_route_handler($nonconformityLink, 'QM Nonconformity', nonconformityNames);
        }
    });
}


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
	if (frm.doc.__islocal) {
		return;
	}
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

	frm.add_custom_button(__('New Version'), function() {
        const dialog = new frappe.ui.Dialog({
            title: __('New Version'),
            fields: [
                {
                    fieldname: 'new_version',
                    label: __('New Version Number'),
                    fieldtype: 'Data',
                    reqd: 1,
                    default: frm.doc.version || ''
                },
                {
                    fieldname: 'entry_type',
                    label: __('Log Book Type'),
                    fieldtype: 'Select',
                    options: [
                        '',
                        'Bugfix',
                        'Update',
                        '(Re-)Validation',
                        'Audit Trail Review',
                        'Other'
                    ].join('\n'),
                    reqd: 1,
                    default: 'Update'
                },
                {
                    fieldname: 'date',
                    label: __('Date of occurence'),
                    fieldtype: 'Date',
                    reqd: 1,
                    default: frappe.datetime.get_today()
                },
                {
                    fieldname: 'description',
                    label: __('Description of change'),
                    fieldtype: 'Small Text',
                    reqd: 1
                }
            ],
            primary_action_label: __('Create'),
            primary_action: function(values) {
                if (values.new_version === frm.doc.version) {
                    frappe.msgprint(__('Please provide a version number different from the current version.'));
                    return;
                }

                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_computerised_system.qm_computerised_system.create_logbook_entry',
                    'freeze': true,
                    'freeze_message': __('Creating Log Book entry and updating version...'),
                    'args': {
                        'qm_computerised_system': frm.doc.name,
                        'entry_type': values.entry_type,
                        'description': values.description,
                        'date': values.date
                    },
                    callback: function(r) {
                        if (r.exc) {
                            return;
                        }
                        dialog.hide();
                        frm.set_value('version', values.new_version);
                        frm.save().then(() => {
                            frappe.show_alert({
                                message: __('New version set and Log Book entry created.'),
                                indicator: 'green'
                            });
                        });
                    }
                });
            }
        });

        dialog.show();
	}, __('Create'));

	frm.add_custom_button(__('Log Book Entry'), function() {
		frappe.new_doc('QM Log Book', {
			document_type: frm.doc.doctype,
			document_name: frm.doc.name
		});
	}, __('Create'));
}


function unlock_fields(frm, fields) {
    fields.forEach(field => {
        frm.set_df_property(field, 'read_only', 0);
    });
}


function lock_fields(frm, fields) {
    fields.forEach(field => {
        frm.set_df_property(field, 'read_only', 1);
    });
}


function apply_field_permissions(frm, isProcessOwner) {
    const status = frm.doc.status;
    const user = frappe.session.user;
    const roles = frappe.user_roles;

    const is_qau = roles.includes('QAU');
    const is_responsible_user = frm.doc.responsible_user === user;
    const is_owner_or_responsible_user = isProcessOwner || is_responsible_user;

    const fields_in_scope = [
        'cs_name',
        'description',
        'qm_process',
        'company',
        'gamp5_class',
        'regulatory_classification',
        'cs_type',
        'primary_version_control_method',
        'version',
        'responsible_user'
    ];

    // Start from unlocked, then apply matrix-based locks.
    unlock_fields(frm, fields_in_scope);

    // Decommissioned: all listed fields are locked for all roles.
    if (status === 'Decommissioned') {
        lock_fields(frm, fields_in_scope);
        return;
    }

    // Validated:
    // - QAU: only version is locked.
    // - QM Process Owner / Responsible User: all listed fields except responsible_user are locked.
    if (status === 'Validated') {
        if (is_qau) {
            lock_fields(frm, ['version']);
            return;
        }

        if (is_owner_or_responsible_user) {
            lock_fields(frm, [
                'cs_name',
                'description',
                'qm_process',
                'company',
                'gamp5_class',
                'regulatory_classification',
                'cs_type',
                'primary_version_control_method',
                'version'
            ]);
            return;
        }

        // Non-target roles should not edit these fields once validated.
        lock_fields(frm, fields_in_scope);
    }
}
