frappe.ui.form.on('Quotation Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});

frappe.ui.form.on('Quotation', {
    refresh(frm){
        // run code with a delay because the core framework code is slower than the refresh trigger and would overwrite it
        setTimeout(function(){
            cur_frm.fields_dict['customer_address'].get_query = function(doc) {          //gets field you want to filter
                return {
                    filters: {
                        "link_doctype": "Customer",
                        "link_name": cur_frm.doc.party_name,
                        "address_type": "Billing"
                    }
                }
            } 
        },500);
        
        hide_in_words();
    },
    
    before_save(frm) {
        if (frm.doc.product_type == "Oligos" || frm.doc.product_type == "Material") {
            var category = "Material";
        } else {
            var category = "Service";
        };
        var category = "Service";
        if (frm.doc.oligos != null && frm.doc.oligos.length > 0 ) {
            category = "Material";
        }; 
        update_taxes(frm.doc.company, frm.doc.party_name, frm.doc.shipping_address_name, category);
    }
});
