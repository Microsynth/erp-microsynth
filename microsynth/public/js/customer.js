try {
    cur_frm.dashboard.add_transactions([
        {
            'label': 'Pre Sales',
            'items': ['Standing Quotation']
        },
        {
            'label': 'Quality Management',
            'items': ['QM Document']
        }
    ]);
} catch { /* do nothing for older versions */ }


function has_credits(frm) {
    var return_value;
    frappe.call({
        'method': 'microsynth.microsynth.credits.has_credits',
        'args': {
            'customer': frm.doc.name
        },
        "async": false,
        'callback': function(response) {
            return_value = response.message;
        }
    });
    return return_value;
}


frappe.ui.form.on('Customer', {
    refresh(frm) {
        // show button "Contacts" if Customer has not Status "Disabled", directing to the Customer Finder
        if (frm.doc.disabled != 1) {
            frm.add_custom_button(__("Contacts"), function() {
                frappe.set_route("query-report", "Customer Finder", {'customer_id': frm.doc.name});
            });
        }
        // show button "Customer Credits" only if Customer has credits for any company
        if (has_credits(frm)) { 
            frm.add_custom_button(__("Customer Credits"), function() {
                frappe.set_route("query-report", "Customer Credits", {'customer': frm.doc.name, 'company': frm.doc.default_company});
            });
        };   
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
        if ((!frm.doc.__islocal) && (frm.doc.invoicing_method === "Email") && (!frm.doc.invoice_to) && (!frm.doc.disabled)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'orange',
                message: __("Please select an <strong>invoice to</strong> contact with an email address.")
            });
        }
    },
    validate(frm) {
        if ((!frm.doc.__islocal) && (frm.doc.invoicing_method === "Email") && (!frm.doc.invoice_to) && (!frm.doc.disabled)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'red',
                message: __("Please select an <strong>invoice to</strong> contact with an email address.<br>Changes are <strong>not saved</strong>.")
            });
            frappe.validated=false;
        }
    },
    after_save(frm) {
        if (!frm.doc.disabled) {
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