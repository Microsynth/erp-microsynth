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
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Payment Reminder"), function() {
                create_payment_reminder(frm);
            }, __("Create") );
        }
        if ((!frm.doc.__islocal)
            && ['ARIBA', 'Paynet', 'GEP', 'Chorus', 'X-Rechnung', 'Scientist'].includes(frm.doc.invoicing_method)
            && (!frm.doc.invoice_network_id)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'orange',
                message: __("Please set the Invoice Network ID or select an Invoicing Method that does not require an Invoice Network ID.")
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
        if (frm.doc.tax_id && frm.doc.customer_type != 'Individual') {
            verify_tax_id(frm.doc.tax_id);
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
    },
    tax_id: function(frm) {
        if (frm.doc.tax_id && frm.doc.customer_type != 'Individual') {
            verify_tax_id(frm.doc.tax_id)
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


function create_payment_reminder(frm) {
    // ask for which company relation
    frappe.prompt([
            {
                'fieldname': 'company', 
                'fieldtype': 'Link', 
                'label': __('Company'), 
                'options': 'Company', 
                'default': frappe.defaults.get_user_default("Company"),
                'reqd': 1}  
        ],
        function(values) {
            frappe.call({
                'method': 'erpnextswiss.erpnextswiss.doctype.payment_reminder.payment_reminder.create_reminder_for_customer',
                'args': {
                    'customer': frm.doc.name,
                    'company': values.company,
                    'auto_submit': 0,
                    'max_level': 4
                },
                'callback': function(response) {
                    if (response.message) {
                        frappe.show_alert( __("Reminder created") + 
                            ": <a href='/desk#Form/Payment Reminder/" + 
                            response.message + "'>" + response.message + 
                            "</a>"
                        );
                    } else {
                        frappe.show_alert( __("No overdue invoices (or error)") )
                    }
                }
            });
        },
        __('Select Company'),
        __('OK')
    );
}


function verify_tax_id(tax_id) {
    if (!cur_frm.doc.tax_id.startsWith('CH') &&
        !cur_frm.doc.tax_id.startsWith('GB') &&
        !cur_frm.doc.tax_id.startsWith('IS') &&
        !cur_frm.doc.tax_id.startsWith('TR')) {
        frappe.call({
            method: 'erpnextaustria.erpnextaustria.utils.check_uid',
            args: {
                uid: tax_id
            },
            async: false,
            callback: function(r) {
                if (r.message != true) {
                    frappe.msgprint( __("Invalid Tax ID") );
                    frappe.validated = false;
                } else {
                    frappe.show_alert( __("Tax ID valid") );
                }
            }
        });
    }
}
