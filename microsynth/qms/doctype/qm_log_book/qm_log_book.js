// Copyright (c) 2026, Microsynth
// For license information, please see license.txt


frappe.ui.form.on('QM Log Book', {
    refresh: function(frm) {

        if (frappe.route_options) {
            if (frappe.route_options.document_type) {
                frm.set_value('document_type', frappe.route_options.document_type);
            }
            if (frappe.route_options.document_name) {
                frm.set_value('document_name', frappe.route_options.document_name);
            }
        }
        if (frm.doc.__islocal && !frm.doc.document_name) {
            frm.dashboard.add_comment(__("Please create this Log Book Entry from the QM Instrument."), "red", true);
        }
        if (!frm.doc.__islocal && frm.doc.document_type && frm.doc.document_name) {
            // do not allow to relink the log book entry to another document after it has been created
            frm.set_df_property("document_name", "read_only", true);
        }
        if (frm.doc.status != "Draft") {
            // Lock all fields
            frm.fields.forEach(field => {
                if (field.df?.fieldname) {
                    frm.set_df_property(field.df.fieldname, 'read_only', 1);
                }
            });
        }

        if (frm.doc.status === "Closed") {
            // Remove Cancel button
            setTimeout(() => {
                frm.page.wrapper.find('.btn-secondary').hide();
            }, 100);
        }

        if (frm.doc.document_type === "QM Instrument" && frm.doc.status === "To Review" && frm.doc.docstatus === 1) {
            if (frappe.user_roles.includes('QAU')) {
                allow_write_access(frm);
                show_approve_button(frm);
            } else {
                // Check if the user is the PV of the QM Process of the linked document
                frappe.call({
                    'method': "microsynth.qms.doctype.qm_log_book.qm_log_book.is_user_process_owner",
                    'args': {
                        'log_book_id': frm.doc.name,
                        'user': frappe.session.user
                    },
                    'callback': function(r) {
                        if (r.message === true) {
                            allow_write_access(frm);
                            // Check if the linked QM Instrument has regulatory_classification "GMP"
                            frappe.call({
                                'method': "frappe.client.get_value",
                                'args': {
                                    'doctype': "QM Instrument",
                                    'name': frm.doc.document_name,
                                    'fieldname': "regulatory_classification"
                                },
                                'callback': function(r) {
                                    if (r.message && r.message.regulatory_classification === "non-GMP") {
                                        show_approve_button(frm);
                                    }
                                }
                            });
                        }
                    }
                });
            }
        }

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();
    }
});


function allow_write_access(frm) {
    frm.set_df_property("entry_type", "read_only", 0);
    frm.set_df_property("date", "read_only", 0);
    frm.set_df_property("description", "read_only", 0);
    frm.set_df_property("costs", "read_only", 0);
}


function show_approve_button(frm) {
    // add button "Approve and Close" that sets the status to "Closed"
    frm.add_custom_button(__('Approve and Close'), function() {
        frm.set_value('status', 'Closed');
        frm.save();
        frm.refresh();
        frappe.show_alert(__('Log Book Entry has been closed.'));
    }).addClass("btn-success");
}
