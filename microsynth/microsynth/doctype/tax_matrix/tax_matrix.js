// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Tax Matrix', {
    // refresh: function(frm) {

    // }
});

frappe.ui.form.on('Tax Matrix Template Mapping', {
    purchase_tax_template: function(frm, cdt, cdn) {
        let template = frappe.model.get_value(cdt, cdn, "purchase_tax_template");
        if (template) {
            frappe.call({
               'method': "frappe.client.get",
               'args': {
                    "doctype": "Purchase Taxes and Charges Template",
                    "name": template
               },
               'callback': function(response) {
                    frappe.model.set_value(cdt, cdn, "purchase_company", response.message.company);
               }
            });
        }
    }
});
