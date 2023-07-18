try {
    cur_frm.dashboard.add_transactions([
        {
            'label': 'Pre Sales',
            'items': ['Standing Quotation']
        }
    ]);
} catch { /* do nothing for older versions */ }

frappe.ui.form.on('Customer', {
    refresh(frm) {
        if ((!frm.doc.__islocal) && (frm.doc.default_price_list)) {
            frm.add_custom_button(__("Gecko Export"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.migration.export_customer_to_gecko",
                    "args": {
                        "customer_name":frm.doc.name
                    }
                })
            });
            frm.add_custom_button(__("Price List"), function() {
                frappe.set_route("query-report", "Pricing Configurator", {'price_list': frm.doc.default_price_list});
            });
        }
    },
    after_save(frm) {
        frappe.call({
            "method":"microsynth.microsynth.utils.configure_customer",
            "args": {
                "customer": frm.doc.name
            },
            "callback": function(response) { 
                cur_frm.reload_doc();
            }
        });
    }
});