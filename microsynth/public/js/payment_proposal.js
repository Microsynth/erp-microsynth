frappe.ui.form.on('Payment Proposal', {
    refresh(frm) {
        if (frm.doc.docstatus == 0) {
            setTimeout (set_intermediate_account, 500); // timeout to ensure loading of configuration in custom script
        }
        else if (frm.doc.docstatus == 1) {
            let desired_version = "09";
            frm.add_custom_button(__("Download bank file v" + desired_version), function() {
                frappe.db.get_value("ERPNextSwiss Settings", "ERPNextSwiss Settings", ["xml_version"], function(value) {
                    let original_xml_version = value['xml_version'];
                    if (original_xml_version != desired_version) {
                        frappe.call({
                            'method': 'microsynth.microsynth.utils.set_xml_version',
                            "args": {
                                "xml_version": desired_version
                            },
                            'callback': function(r) {
                                if (r.message.success) {
                                    frappe.call({
                                        'method': 'create_bank_file',
                                        'doc': frm.doc,
                                        'callback': function(r) {
                                            if (r.message) {
                                                // prepare the xml file for download
                                                download("payments.xml", r.message.content);
                                                // reset XML version
                                                frappe.call({
                                                    'method': 'microsynth.microsynth.utils.set_xml_version',
                                                    "args": {
                                                        "xml_version": original_xml_version
                                                    },
                                                    'callback': function(r) {
                                                        if (r.message.success) {
                                                            frappe.show_alert("Successfully reset the XML version to " + original_xml_version + ".");     
                                                        } else {
                                                            frappe.throw('Unable to reset XML version to ' + original_xml_version + ':<br>' + r.message.message);
                                                        }
                                                    }
                                                });
                                            } 
                                        }
                                    });
                                } else {
                                    frappe.throw('Unable to set XML version to ' + desired_version + ':<br>' + r.message.message);
                                }
                            }
                        });
                    } else {
                        frappe.show_alert("The XML version has already been set to " + desired_version + ", please use the blue button 'Download bank file'.");
                    }
                });
            });
        }
    },
});

function set_intermediate_account() {
    if (locals.account_matrix[cur_frm.doc.company].intermediate_account) {
        cur_frm.set_value("use_intermediate", 1);
        cur_frm.set_value("intermediate_account", locals.account_matrix[cur_frm.doc.company].intermediate_account);
    }
}
