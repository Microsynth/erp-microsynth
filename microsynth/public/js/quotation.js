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

        // fetch Sales Manager from Customer if not yet set
        if (frm.doc.__islocal && (!frm.doc.sales_manager || frm.doc.sales_manager == "")) {
            frappe.call({
                'method': 'frappe.client.get_value',
                'args': {
                    'doctype': 'Customer',
                    'fieldname': 'account_manager',
                    'filters': {
                        'name': cur_frm.doc.party_name,
                    }
                },
                callback: function(r){
                    frm.doc.sales_manager = r.message.account_manager;
                }
            });
        }
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
        
        // assert customer master fields on initial save
        if (frm.doc.__islocal) {
            assert_customer_fields(frm);
        }
        
        if (frm.doc.shipping_address_name && frm.doc.shipping_address_name != "") {
            update_taxes(frm.doc.company, frm.doc.party_name, frm.doc.shipping_address_name, category, frm.doc.transaction_date);
        } else {
            frappe.msgprint(__("Check shipping address"), __("Quotation"));
        }
    }
});

/* this function will pull
 * territory, currency and selling_price_list 
 * from the customer master data */
function assert_customer_fields(frm) {
    if ((frm.doc.quotation_to === "Customer") && (frm.doc.party_name)) {
        frappe.call({
            'method': "frappe.client.get",
            'args': {
                'doctype': "Customer",
                'name': frm.doc.party_name
            },
            'asyc': false,
            'callback': function(r) {
                var customer = r.message;
                if (customer.territory) { cur_frm.set_value("territory", customer.territory); }
                if (customer.default_currency) { cur_frm.set_value("currency", customer.default_currency); }
                if (customer.default_price_list) {cur_frm.set_value("selling_price_list", customer.default_price_list); }
            }
        });
    }
}
