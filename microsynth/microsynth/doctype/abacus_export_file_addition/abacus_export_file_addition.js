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
