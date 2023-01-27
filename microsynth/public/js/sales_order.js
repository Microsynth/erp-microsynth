/* Custom script extension for Sales Order */
frappe.ui.form.on('Sales Order', {
    refresh(frm) {		
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Print Delivery Label"), function() {
                frappe.call({
                    "method": "microsynth.microsynth.labels.print_shipping_label",
                    "args": {
                        "sales_order_id": frm.doc.name
                    }
                })
            });
        } else {
            prepare_naming_series(frm);             // common function
        }
    
    },
    before_save(frm) {
        var category = "Service";
        if (frm.doc.oligos != null && frm.doc.oligos.length > 0 ) {
            category = "Material";
        };         
        update_taxes(frm.doc.company, frm.doc.customer, frm.doc.customer_address, category);
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }            
    }
});

frappe.ui.form.on('Sales Order Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});
