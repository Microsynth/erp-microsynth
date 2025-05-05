// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

cur_frm.fields_dict.accounts.grid.get_field('account').get_query =   
    function() {                                                                      
        return {
            filters: {
                "company": cur_frm.doc.company,
                "disabled": 0
            }
        }
    };

frappe.ui.form.on('Abacus Export File Addition', {
    'refresh': function(frm) {
        // download button for submitted documents
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__('Download'), function() {
                frappe.call({
                    'method': "render_transfer_file",
                    'doc': frm.doc,
                    'callback': function(r) {
                        if (r.message) {
                            // prepare the xml file for download
                            console.log(r.message.content);
                            download("transfer_addtnl.xml", r.message.content);
                        } 
                    }
                });
            }).addClass("btn-primary");

            frm.add_custom_button(__('Create new'), function() {
                create_from_existing(frm);
            });
        }
    },
    'validate': function(frm) {
        if ((!frm.doc.accounts) || (frm.doc.accounts.length < 1)) {
            frappe.msgprint( __("Please select at least one account"), __("Validation") );
            frappe.validated=false;
        }
    },
    'from_date': function(frm) {
        if ((frm.doc.from_date) && (frm.doc.to_date) && (frm.doc.from_date > frm.doc.to_date)) {
            cur_frm.set_value('to_date', frm.doc.from_date);
        }
    },
    'to_date': function(frm) {
        if ((frm.doc.from_date) && (frm.doc.to_date) && (frm.doc.from_date > frm.doc.to_date)) {
            cur_frm.set_value('from_date', frm.doc.to_date);
        }
    }
});

function download(filename, content) {
    var element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}


function create_from_existing(frm) {
    var d = new frappe.ui.Dialog({
        'fields': [
            {'fieldname': 'company', 'fieldtype': 'Link', 'options': "Company", 'label': __('Company'), 'read_only': 1, 'default': frm.doc.company},
            {'fieldname': 'from_date', 'fieldtype': 'Date', 'label': __('From date'), 'reqd': 1},
            {'fieldname': 'to_date', 'fieldtype': 'Date', 'label': __('To date'), 'reqd': 1}
        ],
        'primary_action': function(){
            d.hide();
            var values = d.get_values();
            frappe.call({
                'method': "microsynth.microsynth.doctype.abacus_export_file_addition.abacus_export_file_addition.create_from_existing",
                'args':{
                    'dn': frm.doc.name,
                    'from_date': values.from_date,
                    'to_date': values.to_date
                },
                'callback': function(r) {
                    if (r.message) {
                        frappe.set_route("Form", "Abacus Export File Addition", r.message);
                    } else {
                        frappe.show_alert("Internal Error")
                    }
                }
            });
        },
        'primary_action_label': __('Create'),
        'title': __('Create a new AEFA based on ' + frm.doc.name)
    });
    d.show();
}
