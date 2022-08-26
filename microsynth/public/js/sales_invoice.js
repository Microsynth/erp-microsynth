/* Custom script extension for Sales Invoice */
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
		prepare_naming_series(frm);				// common function
	},
    company(frm) {
		set_naming_series(frm);					// common function
    }
});

frappe.ui.form.on('Sales Invoice Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});
