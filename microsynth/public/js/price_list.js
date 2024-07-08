frappe.ui.form.on('Price List', {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            // link to pricing configurator
            frm.add_custom_button(__("Price List"), function() {
                frappe.set_route("query-report", "Pricing Configurator", {'price_list': frm.doc.name});
            });
            // show customers with this price list
            frm.add_custom_button(__("Customers"), function() {
                frappe.set_route("List", "Customer", {"default_price_list": frm.doc.name, "disabled": 0});
            });
        }
    }
});
