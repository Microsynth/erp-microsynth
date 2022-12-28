frappe.ui.form.on('Quotation Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});

frappe.ui.form.on('Quotation', {
    before_save(frm) {
        update_taxes(frm);
    }
});

function update_taxes(frm) {
    var category = "Service";
    if (frm.doc.oligos.length > 0 ) {
        category = "Material";
    }; 
    
    frappe.call({
        "method": "microsynth.microsynth.utils.find_tax_template",
        "args": {
            "company": frm.doc.company,
            "customer": frm.doc.party_name,
            "customer_address": frm.doc.customer_address,
            "category": category 
        },
        "async": false,
        "callback": function(response){
            var taxes = response.message;   
            
            cur_frm.set_value("taxes_and_charges", taxes);

            frappe.call({
                "method":"frappe.client.get",
                "args": {
                    "doctype": "Sales Taxes and Charges Template",
                    "name": taxes
                },
                "async": false,
                "callback": function(response){
                    var tax_template = response.message;
                    cur_frm.clear_table("taxes");
                    for (var t = 0; t < tax_template.taxes.length; t++) {
                        var child = cur_frm.add_child('taxes')
                        
                        frappe.model.set_value(child.doctype, child.name, 'charge_type', tax_template.taxes[t].charge_type);
                        frappe.model.set_value(child.doctype, child.name, 'account_head', tax_template.taxes[t].account_head);
                        frappe.model.set_value(child.doctype, child.name, 'description', tax_template.taxes[t].description);
                        frappe.model.set_value(child.doctype, child.name, 'cost_center', tax_template.taxes[t].cost_center);
                        frappe.model.set_value(child.doctype, child.name, 'rate', tax_template.taxes[t].rate);
                    }
                }
            });
        }
    });
}