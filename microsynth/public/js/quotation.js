frappe.ui.form.on('Quotation Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});

frappe.ui.form.on('Quotation', {
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