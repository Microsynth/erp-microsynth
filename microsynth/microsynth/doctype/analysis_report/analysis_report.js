// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('Analysis Report', {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            // Disable removing attachments
            access_protection();
        }
    },
    address: function() {
        if(cur_frm.doc.address) {
            frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {"address_dict": cur_frm.doc.address},
                callback: function(r) {
                    if(r.message) {
                        cur_frm.set_value("address_display", r.message);
                    }
                }
            })
        } else {
            cur_frm.set_value("address_display", "");
        }
    },
});
