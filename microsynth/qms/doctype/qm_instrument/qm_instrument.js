// Copyright (c) 2025, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Instrument', {
    onload: function(frm) {
        frm.set_query('purchase_invoice', function() {
            if (frm.doc.supplier) {
                return {
                    'filters': {
                        'docstatus': 1,
                        'supplier': frm.doc.supplier
                    }
                };
            } else {
                return {
                    'filters': {
                        'docstatus': 1
                    }
                };
            }
        });
    },

    supplier: function(frm) {
        // Clear purchase_invoice when supplier changes
        frm.set_value('purchase_invoice', null);
    },

    category: function(frm) {
        // clear subcategory if category is changed
        frm.set_value('subcategory', null);
    },

    refresh: function(frm) {
        const site_company_mapping = {
            "Balgach": "Microsynth AG",
            "Göttingen": "Microsynth Seqlab GmbH",
            "Lyon": "Microsynth France SAS",
            "Wien": "Microsynth Austria GmbH"
        };
        const company = site_company_mapping[frm.doc.site];

        frm.dashboard.clear_comment();

        if (frm.doc.qm_process && company) {
            frappe.call({
                'method': "microsynth.qms.doctype.qm_instrument.qm_instrument.get_qm_process_owner",
                'args': {
                    'qm_process': frm.doc.qm_process,
                    'company': company
                },
                'callback': function(r) {
                    const isProcessOwner = r.message.includes(frappe.session.user);
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

        if (!frm.doc.__islocal) {
            // display an advanced dashboard
            frappe.call({
                'method': 'get_advanced_dashboard',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('overview', 'options', r.message);
                }
            });
        }

        // filter for category
        frm.fields_dict.category.get_query = function(frm) {
            return {
                'query': 'microsynth.qms.doctype.qm_instrument.qm_instrument.get_allowed_category',
            };
        };
        // filter for subcategory based on category
        frm.fields_dict.subcategory.get_query = function(frm) {
            return {
                'query': 'microsynth.qms.doctype.qm_instrument.qm_instrument.get_allowed_subcategory_for_category',
                'filters': {
                    'category': cur_frm.doc.category
                }
            };
        };

        // remove dashboard doc (+) buttons since the creation of QM Log Book entries does not work correctly when using the (+) button in the dashboard
        var new_btns = document.getElementsByClassName("btn-new");
        for (var i = 0; i < new_btns.length; i++) {
            new_btns[i].style.visibility = "hidden";
        }

        // If the instrument class is A, a (Re-)Qualification is required every 2 years
        // If the instrument class is F, a Verification is required each year and a Calibration every 5 years
        // If the instrument class if T or W, a Verification is required each year
        // If the instrument is overdue, show an red alert in the dashboard
        // If the instrument is due the next 30 days, show an orange alert in the dashboard
        if (!frm.doc.__islocal && frm.doc.instrument_class && ['A', 'F', 'T', 'W'].includes(frm.doc.instrument_class.charAt(0))) {
            frappe.call({
                'method': "microsynth.qms.doctype.qm_instrument.qm_instrument.get_due_qualifications",
                'args': {
                    'instrument_name': frm.doc.name,
                    'instrument_class': frm.doc.instrument_class,
                    'acquisition_date': frm.doc.acquisition_date
                },
                'callback': function(r) {
                    const qualifications = r.message || [];
                    console.log(qualifications);

                    qualifications.forEach(q => {
                        const due_date = q.due_date;
                        const qualification_type = q.qualification_type;

                        if (due_date) {
                            const days_diff = frappe.datetime.get_diff(due_date, frappe.datetime.get_today());

                            if (days_diff < 0) {
                                frm.dashboard.add_comment(
                                    `<b>${qualification_type} overdue since ${due_date}</b>`,
                                    'red',
                                    true
                                );
                            } else if (days_diff <= 30) {
                                frm.dashboard.add_comment(
                                    `<b>${qualification_type} due on ${due_date}</b>`,
                                    'orange',
                                    true
                                );
                            }
                        }
                    });
                }
            });
        }
    }
});


function get_allowed_transitions(frm, isProcessOwner) {
    const status = frm.doc.status;
    const roles = frappe.user_roles;
    const user = frappe.session.user;

    const is_purchaser = roles.includes('Purchase User') || roles.includes('Purchase Manager');
    const is_qau = roles.includes('QAU');
    const is_manager = [frm.doc.instrument_manager, frm.doc.deputy_instrument_manager].includes(user);

    const is_gmp = frm.doc.regulatory_classification === 'GMP';
    const is_non_gmp_freezer = frm.doc.instrument_class?.startsWith('F') && !is_gmp;
    const is_non_gmp_a_b_c =
        (frm.doc.instrument_class?.startsWith('A') ||
         frm.doc.instrument_class?.startsWith('B') ||
         frm.doc.instrument_class?.startsWith('C')) && !is_gmp;

    const RULES = [
        {
            condition: () => is_qau,
            transitions: [
                ['Active', 'Blocked'],
                ['Blocked', 'Active'],
                ['Blocked', 'Decommissioned'],
                ['Active', 'Decommissioned'],
                ['Decommissioned', 'Disposed'],
                ['Decommissioned', 'Active'],
                ['Unapproved', 'Active']
            ]
        },
        {
            condition: () => (is_manager || isProcessOwner) && is_non_gmp_a_b_c,
            transitions: [
                ['Unapproved', 'Active'],
                ['Decommissioned', 'Active'],
                ['Decommissioned', 'Disposed'],
                ['Blocked', 'Active'],
                ['Blocked', 'Decommissioned'],
                ['Active', 'Decommissioned']
            ]
        },
        {
            condition: () => (is_manager || isProcessOwner) && is_non_gmp_freezer,
            transitions: [
                ['Active', 'Decommissioned'],
                ['Blocked', 'Active'],
                ['Decommissioned', 'Disposed'],
                ['Blocked', 'Decommissioned']
            ]
        },
        {
            condition: () => is_purchaser,
            transitions: [['Decommissioned', 'Disposed']]
        },
        {
            condition: () => true,
            transitions: [['Active', 'Blocked']]
        }
    ];
    const transitions = new Set();

    RULES.forEach(rule => {
        if (rule.condition()) {
            rule.transitions.forEach(([f, t]) => {
                transitions.add(`${f}|${t}`);
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
        'Blocked': 'Block Instrument',
        'Active': 'Activate',
        'Decommissioned': 'Decommission',
        'Disposed': 'Dispose'
    };
    transitions.forEach(([from, to]) => {
        const label =
            (from === 'Unapproved' && to === 'Active')
                ? 'Approve and Release'
                : labels[to] || to;

        const color =
            (to === 'Blocked' || to === 'Decommissioned' || to === 'Disposed')
                ? 'btn-danger'
                : 'btn-success';

        frm.add_custom_button(__(label), function() {
            frm.set_value('status', to);

            frm.save().then(() => {
                if (frm.doc.instrument_class?.startsWith('A') && frm.doc.regulatory_classification === 'GMP' && to === 'Blocked') {
                    frappe.call({
                        'method': "microsynth.qms.doctype.qm_instrument.qm_instrument.create_logbook_entry",
                        'args': {
                            'qm_instrument': frm.doc.name,
                            'entry_type': 'Other',
                            'description': 'Instrument was blocked.',
                            'date': frappe.datetime.get_today()
                        },
                        'callback': function(r) {
                            if (r.message) {
                                frappe.show_alert(__('Status changed to "{0}" and Log Book entry {1} created', [to, r.message]), 'success');
                            } else {
                                frappe.show_alert(__('Status changed to "{0}" but failed to create Log Book entry', [to]), 'error');
                            }
                        }
                    });
                } else {
                    frappe.show_alert(__('Status changed to "{0}"', [to]));
                }
            });
        }).addClass(color);
    });

    const is_purchaser = frappe.user_roles.includes('Purchase User') || frappe.user_roles.includes('Purchase Manager');
    const is_qau = frappe.user_roles.includes('QAU');
    const is_manager = frm.doc.instrument_manager === frappe.session.user || frm.doc.deputy_instrument_manager === frappe.session.user;

    if (!frm.doc.__islocal) {
        // Add button "View > Log Book" to open the QM Log Book list if the document is not local
        frm.add_custom_button(__('Log Book'), function() {
            frappe.set_route('List', 'QM Log Book', { 'document_type': frm.doc.doctype, 'document_name': frm.doc.name });
        }, __('View'));

        // Add button Create > Log Book Entry
        frm.add_custom_button(__('Log Book Entry'), function() {
            frappe.new_doc('QM Log Book', {
                document_type: frm.doc.doctype,
                document_name: frm.doc.name
            });
        }, __('Create'));

        // Add button "Add/Change Location" if user is Purchaser, QAU, instrument_manager or deputy_instrument_manager
        if ((is_purchaser && frm.doc.status === 'Unapproved')
            || ((is_qau || is_manager || isProcessOwner)
                && !['Decommissioned', 'Disposed'].includes(frm.doc.status)))
            {
            const button_label = frm.doc.location ? 'Change Location' : 'Add Location';
            frm.add_custom_button(__(button_label), function() {
                show_location_dialog(frm);
            });
        }
    }
}


function lock_all_fields(frm) {
    frm.fields.forEach(field => {
        if (field.df?.fieldname) {
            frm.set_df_property(field.df.fieldname, 'read_only', 1);
        }
    });
    cur_frm.get_field("qm_documents").grid.fields_map['qm_document'].read_only = 1;
    cur_frm.get_field("qm_documents").grid.fields_map['title'].read_only = 1;
}


function unlock_all_fields(frm) {
    const fields_to_unlock = [
        'instrument_name',
        'instrument_class',
        'category',
        'instrument_manager',
        'qm_process',
        'site',
        'regulatory_classification',
        'subcategory',
        'deputy_instrument_manager',
        'serial_no',
        'manufacturer',
        'software_version',
        'has_service_contract',
        'supplier',
        'acquisition_date',
        'purchase_invoice',
        'location',
        'qm_documents',
    ];
    fields_to_unlock.forEach(field => {
        frm.set_df_property(field, 'read_only', 0);
    });
}


function lock_fields(frm, fields) {
    fields.forEach(field => {
        frm.set_df_property(field, 'read_only', 1);
    });
}


function apply_field_permissions(frm, isProcessOwner) {
    const { status, instrument_manager, deputy_instrument_manager } = frm.doc;
    const is_local = frm.doc.__islocal;
    const user = frappe.session.user;
    const roles = frappe.user_roles;
    const is_qau = roles.includes('QAU');
    const is_manager = [instrument_manager, deputy_instrument_manager].includes(user);
    const is_purchaser = (roles.includes('Purchase User') || roles.includes('Purchase Manager')) && !is_qau && !is_manager && !isProcessOwner;

    const isPrivilegedUser = (
        is_purchaser ||
        is_qau ||
        is_manager ||
        isProcessOwner
    );
    const isLockedStatus = ['Decommissioned', 'Disposed'].includes(status);

    // Lock all fields
    if (
        (!is_local && !isPrivilegedUser) ||
        (is_purchaser && status !== 'Unapproved') ||
        isLockedStatus
    ) {
        lock_all_fields(frm);
        return;
    }
    // Start from unlocked, then apply partial locks
    unlock_all_fields(frm);

    // Partial lock
    if (isPrivilegedUser && status !== 'Unapproved') {
        lock_fields(frm, [
            'serial_no',
            'manufacturer',
            'supplier',
            'purchase_invoice',
            'acquisition_date',
            'instrument_class'
        ]);
    }
}


function show_location_dialog(frm) {
    const dialog_title = frm.doc.location ? __("Change existing Location") : __("Add a Location");
    const d = new frappe.ui.Dialog({
        'title': dialog_title,
        'fields': [
            {
                label: __("Subsidiary"),
                fieldname: "subsidiary",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => ({
                    filters: {
                        parent_location: ["in", ["", null]]
                    }
                }),
                default: frm.doc.site || "Balgach",
                read_only: frm.doc.site ? true : false,
                onchange: () => {
                    // Auto-clear dependents
                    d.set_value("floor", "");
                    d.set_value("room", "");
                    d.set_value("destination", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Floor"),
                fieldname: "floor",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => {
                    return d.get_value("subsidiary")
                        ? { filters: { parent_location: d.get_value("subsidiary") } }
                        : {};
                },
                onchange: () => {
                    d.set_value("room", "");
                    d.set_value("destination", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Room"),
                fieldname: "room",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => {
                    return d.get_value("floor")
                        ? { filters: { parent_location: d.get_value("floor") } }
                        : {};
                },
                onchange: () => {
                    d.set_value("destination", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Destination"),
                fieldname: "destination",
                fieldtype: "Link",
                options: "Location",
                reqd: false,
                get_query: () => {
                    return d.get_value("room")
                        ? { filters: { parent_location: d.get_value("room") } }
                        : {};
                }
            }
        ],
        'primary_action_label': __("Save"),
        primary_action(values) {
            // Determine the most specific selected location
            let chosen =
                values.destination ||
                values.room ||
                values.floor ||
                values.subsidiary;

            if (!chosen) {
                frappe.msgprint(__("No location selected"));
                return;
            }
            // Save to field and close dialog
            frm.set_value("location", chosen);
            frm.save();
            d.hide();
        }
    });
    d.show();

    // Initialize states: disable child fields at start
    refresh_field_states(d);
}


function refresh_field_states(d) {
    // Retrieve values
    const subsidiary = d.get_value("subsidiary");
    const floor = d.get_value("floor");
    const room = d.get_value("room");

    // Enable/disable based on hierarchy
    d.get_field("floor").df.read_only = !subsidiary;
    d.get_field("room").df.read_only = !floor;
    d.get_field("destination").df.read_only = !room;
    d.refresh();
}
