/* Custom script extension for Sales Order */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Fulfillment"),
        'items': ["Tracking Code"]
    }
]);


/* Custom script extension for Sales Order */
frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        // remove Menu > Email if document is not valid
        if (frm.doc.docstatus != 1) {
            var target ="span[data-label='" + __("Email") + "']";
            $(target).parent().parent().remove();
        }

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
        
        hide_in_words();
    },
    before_save(frm) {
        if (frm.doc.product_type == "Oligos" || frm.doc.product_type == "Material") {
            var category = "Material";
        } else {
            var category = "Service";
        };
        if (frm.doc.oligos != null && frm.doc.oligos.length > 0 ) {
            category = "Material";
        };         
        update_taxes(frm.doc.company, frm.doc.customer, frm.doc.shipping_address_name, category, frm.doc.delivery_date);
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
