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
        };
        if ((frm.doc.invoicing_method === "Email") && (!frm.doc.invoice_to)) {
            fetch_primary_contact(frm);
        }
    },
    validate(frm) {
        if ((!frm.doc.__islocal) && (frm.doc.invoicing_method === "Email") && (!frm.doc.invoice_to)) {
            frappe.msgprint( __("Please select an invoice contact"), __("Validation") );
            frappe.validated=false;
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

function fetch_primary_contact(frm) {
    frappe.call({
        'method': 'erpnextswiss.scripts.crm_tools.get_primary_customer_contact',
        'args': {
            'customer': frm.doc.name
        },
        'callback': function(r) {
            if (r.message) {
                var contact = r.message;
                cur_frm.set_value("invoice_to", contact.name);
            } 
        }
    });
}