frappe.ui.form.on('Price List', {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Price List"), function() {
                frappe.set_route("query-report", "Pricing Configurator", {'price_list': frm.doc.name});
            });
        }
    }
});
