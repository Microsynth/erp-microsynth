/* Custom script extension for Delivery Note */
frappe.ui.form.on('Delivery Note', {
    refresh(frm) {
        prepare_naming_series(frm);				// common function
        
        hide_in_words();
    },
    company(frm) {
        set_naming_series(frm);					// common function
    }
});

frappe.ui.form.on('Delivery Note Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});
