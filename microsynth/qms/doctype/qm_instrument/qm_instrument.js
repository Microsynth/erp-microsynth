// Copyright (c) 2025, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Instrument', {
    refresh: function(frm) {
        // Set all fields to read-only if user is not QAU, System Manager, instrument_manager, or deputy_instrument_manager
        const user = frappe.session.user;
        const isQAU = frappe.user_roles.includes('QAU');
        const isManager = frm.doc.instrument_manager === user;
        const isDeputy = frm.doc.deputy_instrument_manager === user;

        if (!frm.doc.__islocal && !isQAU && !isManager && !isDeputy && !frappe.user_roles.includes('System Manager')) {
            frm.fields.forEach(field => {
                if (field.df && field.df.fieldname) {
                    console.log(`Setting field ${field.df.fieldname} to read-only`);
                    frm.set_df_property(field.df.fieldname, 'read_only', 1);
                }
            });
        }

        if (!frm.doc.__islocal && frm.doc.status !== 'Out of order') {
            frm.add_custom_button(__('Block Instrument'), function() {
                frm.set_value('status', 'Out of order');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Out of order".'));
            }).addClass("btn-danger");
        }

        // Add Button Create > Log Book Entry
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Log Book Entry'), function() {
                frappe.new_doc('QM Log Book', {
                    document_type: frm.doc.doctype,
                    document_name: frm.doc.name
                });
            }, __('Create'));
        }

        // Add a green button "Activate" (in status "Out of order") or "Release" (in status "Unapproved") that is only visible for users with the role "QAU" or the (deputy) instrument_manager, and only if the status is "Out of order"
        if (!frm.doc.__islocal && (frm.doc.status === 'Out of order' || frm.doc.status === 'Unapproved') && (isQAU || isManager || isDeputy)) {
            const buttonLabel = frm.doc.status === 'Out of order' ? 'Activate' : 'Approve and Release';
            frm.add_custom_button(__(buttonLabel), function() {
                frm.set_value('status', 'Active');
                frm.save();
                frm.refresh();
                frappe.show_alert(__('Instrument has been set to Status "Active".'));
            }).addClass("btn-success");
        }
    }
});
