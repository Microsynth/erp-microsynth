// Copyright (c) 2025, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Instrument', {
    refresh: function(frm) {
        const isLocal = frm.doc.__islocal;
        const status = frm.doc.status;
        const user = frappe.session.user;
        const isPurchaser = frappe.user_roles.includes('Purchase User') || frappe.user_roles.includes('Purchase Manager');
        const isQAU = frappe.user_roles.includes('QAU');
        const isManager = frm.doc.instrument_manager === user;
        const isDeputy = frm.doc.deputy_instrument_manager === user;
        const isSystemManager = frappe.user_roles.includes('System Manager');

        // Set all fields to read-only if user is not Purchaser, QAU, System Manager, instrument_manager, or deputy_instrument_manager
        if (!isLocal && !isPurchaser && !isQAU && !isManager && !isDeputy && !isSystemManager) {
            frm.fields.forEach(field => {
                if (field.df && field.df.fieldname) {
                    console.log(`Setting field ${field.df.fieldname} to read-only`);
                    frm.set_df_property(field.df.fieldname, 'read_only', 1);
                }
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
        if (!isLocal && status === 'Out of order' && (isQAU || isManager || isDeputy)) {
            frm.add_custom_button(__('Archive'), function() {
                frm.set_value('status', 'Archived');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Archived".'));
            }).addClass("btn-danger");
        }

        // Add a red button "Dispose" that is only visible for users with the role "QAU" or the (deputy) instrument_manager, and only if the status is "Out of order" or "Archived"
        if (!isLocal && (status === 'Out of order' || status === 'Archived') && (isQAU || isManager || isDeputy)) {
            frm.add_custom_button(__('Dispose'), function() {
                frm.set_value('status', 'Disposed');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Disposed".'));
            }).addClass("btn-danger");
        }

        // Add a green button "Activate" (in status "Out of order" or "Archived") or "Approve and Release" (in status "Unapproved") that is only visible for users with the role "QAU" or the (deputy) instrument_manager, and only if the status is "Out of order" or "Unapproved"
        if (!isLocal && (status === 'Out of order' || status === 'Archived' || status === 'Unapproved') && (isQAU || isManager || isDeputy)) {
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
    },
    category: function(frm) {
        // clear subcategory if category is changed
        frm.set_value('subcategory', null);
    }
});
