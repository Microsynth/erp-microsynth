// Copyright (c) 2025, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Instrument', {
    onload: function(frm) {
        frm.set_query('purchase_invoice', function() {
            if (frm.doc.supplier) {
                return {
                    filters: {
                        docstatus: 1,
                        supplier: frm.doc.supplier
                    }
                };
            } else {
                return {
                    filters: {
                        docstatus: 1
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
        apply_permissions(frm, false);  // initial pessimistic state
        const isLocal = frm.doc.__islocal;
        const status = frm.doc.status;
        const user = frappe.session.user;
        const isPurchaser = frappe.user_roles.includes('Purchase User') || frappe.user_roles.includes('Purchase Manager');
        const isQAU = frappe.user_roles.includes('QAU');
        const isManager = frm.doc.instrument_manager === user || frm.doc.deputy_instrument_manager === user;
        const isSystemManager = frappe.user_roles.includes('System Manager');

        const site_company_mapping = {
            "Balgach": "Microsynth AG",
            "Göttingen": "Microsynth Seqlab GmbH",
            "Lyon": "Microsynth France SAS",
            "Wien": "Microsynth Austria GmbH"
        };
        const company = site_company_mapping[frm.doc.site];

        if (frm.doc.qm_process && company) {
            frappe.call({
                'method': "microsynth.qms.doctype.qm_instrument.qm_instrument.get_qm_process_owner",
                'args': {
                    'qm_process': frm.doc.qm_process,
                    'company': company
                },
                'callback': function(r) {
                    const isProcessOwner = (r.message === frappe.session.user);
                    if (isProcessOwner) {
                        apply_permissions(frm, true);  // re-apply with elevated rights
                    }
                }
            });
        }

        // Add button "Add/Change Location" if user is Purchaser, QAU, instrument_manager, or deputy_instrument_manager
        if (!isLocal && (isPurchaser || isQAU || isManager || isSystemManager)) {
            const button_label = frm.doc.location ? 'Change Location' : 'Add Location';
            frm.add_custom_button(__(button_label), function() {
                show_location_dialog(frm);
            });
        }

        // Add a red button "Block Instrument" if the status is "Active"
        if (!isLocal && status === 'Active') {
            frm.add_custom_button(__('Block Instrument'), function() {
                frm.set_value('status', 'Out of order');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Out of order".'));
            }).addClass("btn-danger");
        }

        // Add a red button "Archive" that is only visible for users with the role "QAU" or the (deputy) instrument_manager, and only if the status is "Out of order"
        if (!isLocal && status === 'Out of order' && (isQAU || isManager || isSystemManager)) {
            frm.add_custom_button(__('Archive'), function() {
                frm.set_value('status', 'Archived');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Archived".'));
            }).addClass("btn-danger");
        }

        // Add a red button "Dispose" that is only visible for users with the role "QAU" or the (deputy) instrument_manager, and only if the status is "Out of order" or "Archived"
        if (!isLocal && (status === 'Out of order' || status === 'Archived') && (isQAU || isManager || isSystemManager)) {
            frm.add_custom_button(__('Dispose'), function() {
                frm.set_value('status', 'Disposed');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Disposed".'));
            }).addClass("btn-danger");
        }

        // Add a green button "Activate" (in status "Out of order" or "Archived") or "Approve and Release" (in status "Unapproved") that is only visible for users with the role "QAU" or the (deputy) instrument_manager, and only if the status is "Out of order" or "Unapproved"
        if (!isLocal && (status === 'Out of order' || status === 'Archived' || status === 'Unapproved') && (isQAU || isManager || isSystemManager)) {
            const buttonLabel = (status === 'Out of order' || status === 'Archived') ? 'Activate' : 'Approve and Release';
            frm.add_custom_button(__(buttonLabel), function() {
                frm.set_value('status', 'Active');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Active".'));
            }).addClass("btn-success");
        }

        // Add button Create > Log Book Entry
        if (!isLocal) {
            frm.add_custom_button(__('Log Book Entry'), function() {
                frappe.new_doc('QM Log Book', {
                    document_type: frm.doc.doctype,
                    document_name: frm.doc.name
                });
            }, __('Create'));
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

        // Show storage location path in dashboard if location is set
        if (frm.doc.location) {
            const storage_locations = [frm.doc.location];

            const location_promises = storage_locations.map(location => {
                return frappe.call({
                    method: "microsynth.microsynth.purchasing.get_location_path_string",
                    args: { location_name: location },
                });
            });
            // Wait for all calls to finish
            Promise.all(location_promises).then(results => {
                const paths = results
                    .map(r => r.message)
                    .filter(p => p); // remove empty

                if (!paths.length) return;

                const text = "<b>Location:</b> " + paths.join("<br>");

                // Add permanent green dashboard comment
                frm.dashboard.add_comment(text, 'green', true);
            });
        }
    }
});


function lock_all_fields(frm) {
    frm.fields.forEach(field => {
        if (field.df?.fieldname) {
            frm.set_df_property(field.df.fieldname, 'read_only', 1);
        }
    });
}

function unlock_all_fields(frm) {
    frm.fields.forEach(field => {
        if (field.df?.fieldname) {
            frm.set_df_property(field.df.fieldname, 'read_only', 0);
        }
    });
}

function lock_fields(frm, fields) {
    fields.forEach(field => {
        frm.set_df_property(field, 'read_only', 1);
    });
}

function apply_permissions(frm, isProcessOwner) {
    const { __islocal: isLocal, status, instrument_manager, deputy_instrument_manager } = frm.doc;
    const user = frappe.session.user;
    const roles = frappe.user_roles;

    const isPurchaser = roles.includes('Purchase User') || roles.includes('Purchase Manager');
    const isQAU = roles.includes('QAU');
    const isSystemManager = roles.includes('System Manager');
    const isManager = [instrument_manager, deputy_instrument_manager].includes(user);

    const isPrivilegedUser = (
        isPurchaser ||
        isQAU ||
        isManager ||
        isSystemManager ||
        isProcessOwner
    );

    const isLockedStatus = (
        status?.includes('Decommissioned') ||
        status?.includes('Disposed')
    );

    // Lock all fields
    if (
        (!isLocal && !isPrivilegedUser) ||
        (isPurchaser && status !== 'Unapproved') ||
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
            'aquisition_date',
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
    const destination = d.get_value("destination");

    // Enable/disable based on hierarchy
    d.get_field("floor").df.read_only = !subsidiary;
    d.get_field("room").df.read_only = !floor;
    d.get_field("destination").df.read_only = !room;
    d.refresh();
}
