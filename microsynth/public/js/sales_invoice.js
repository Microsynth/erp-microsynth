/* Custom script extension for Sales Invoice */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Reference"),
        'items': ["Payment Reminder"]
    } // ,
    // {
    //     'label': __("Reference"),
    //     'items': ["Accounting Note"]
    // }
]);


frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        locals.prevdoc_checked = false;
        prepare_naming_series(frm);  // common function

        // remove Menu > Email
        var target ="span[data-label='" + __("Email") + "']";
        $(target).parent().parent().remove();

        // disable keyboard shortcut CTRL + E if document is not valid
        //if (frm.doc.docstatus != 1) {  // TODO: comment in as soon as setting custom shortcut works (see below)
        frappe.ui.keys.off("ctrl+e");
        //}

        frappe.ui.keys.add_shortcut({
            'shortcut': 'ctrl+e',
            'action': function() { 
                open_mail_dialog(frm)
            },
            'description': __('Custom Email shortcut')
        });

        // Custom email dialog
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__("Email"), function() {
                open_mail_dialog(frm);
            }, __("Create"));
        }
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Accounting Note"), function() {
                create_accounting_note(frm);
            }, __("Create"));
        }

        if (frm.doc.docstatus == 0 && frm.doc.net_total > 0 && !frm.doc.__islocal) {
            frappe.db.get_value('Customer', frm.doc.customer, 'customer_credits')
            .then(r => {
                if (r.message.customer_credits != 'blocked'){
                    frm.add_custom_button(__("Allocate credit"), function() {
                        allocate_credits(frm);
                    });
                }
            })
        };
        if ((frm.doc.docstatus == 0) && (frm.doc.total_customer_credit > 0)) {
            frm.add_custom_button(__("Clear credit"), function() {
                clear_credits(frm);
            });
        }
        if (frm.doc.docstatus > 0) {
            frm.add_custom_button(__("Clone"), function() {
                clone(frm);
            });
        };
        if ((frm.doc.docstatus == 1) && (frm.doc.outstanding_amount > 0)) {
            frm.add_custom_button(__("Against Expense Account"), function() {
                close_against_expense(frm);
            }, __("Close"));
        };
        if (frm.doc.__islocal) {
            get_exchange_rate(frm);
            
            cur_frm.set_value("invoice_sent_on", null );        // fresh document cannot be sent out (in case duplicate, ... reset)
        }
        if ((frm.doc.docstatus === 1) && (!frm.doc.is_return) && (!frm.doc.invoice_sent_on)) {
            frm.add_custom_button(__("Transmit"), function() {
                transmit_invoice(frm);
            });
        }
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("ZUGFeRD XML"), function() {
                download_zugferd_xml(frm);
            });
        }
        if (!frm.doc.__islocal) {
            fetch_accounting_notes(frm);
        }

        if (frm.doc.docstatus === 2 && frm.doc.web_order_id) {
            frm.add_custom_button(__("Search valid version"), function() {
                frappe.set_route("List", "Sales Invoice", {"web_order_id": frm.doc.web_order_id, "docstatus": 1});
            });
        }

        if (frm.doc.web_order_id) {
            frm.add_custom_button(__('Sales Orders'), function () {
                frappe.set_route('List', 'Sales Order', { 'web_order_id': frm.doc.web_order_id });
            }, __("View"));

            frm.add_custom_button(__('Delievery Notes'), function () {
                frappe.set_route('List', 'Delivery Note', { 'web_order_id': frm.doc.web_order_id });
            }, __("View"));            
        }

        hide_in_words();

        var time_out = 500;
        if (frm.doc.items)
        {
           time_out += frm.doc.items.length * 100;
        }

        if (frm.doc.__islocal) {
            setTimeout(function () {
                check_prevdoc_rates(cur_frm);
            }, time_out);
        }
        // Clear Customer Credits on this invoice if it has just been duplicated from another invoice
        if (frm.doc.__islocal && frm.doc.amended_from == null && frm.doc.total_customer_credit != 0) {
            clear_credits(frm);
        }
        
        // Allow to create only full credit notes with custom function if a customer credit has been applied.
        if ((frm.doc.docstatus === 1) && (frm.doc.is_return === 0) && (frm.doc.total_customer_credit > 0)) {
            setTimeout(function() {
                cur_frm.remove_custom_button(__("Return / Credit Note"), __("Create"));
                cur_frm.add_custom_button(__("Full Return / Credit Note"), function() {
                    full_return(cur_frm);
                }, __("Create"))
            }, 500);
        }
        // clean up the create menu (obsolete functions in the current process landscape)
        setTimeout(function() {
            cur_frm.remove_custom_button(__("Delivery"), __("Create"));
            cur_frm.remove_custom_button(__("Maintenance Schedule"), __("Create"));
            cur_frm.remove_custom_button(__("Subscription"), __("Create"));
        }, 500);

        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            });
        }

        // prepare for company validation
        if (frm.doc.docstatus === 0) {
            cache_company_key(frm);
        }
        
        // in case of customer credit bookings, display links in the customer credit section
        if ((frm.doc.docstatus === 1) && (frm.doc.total_customer_credit > 0)) {
            display_customer_credit_bookings(frm);
        } else {
            // reset form html, in case of opening the form after a previous credit
            cur_frm.set_df_property('customer_credit_booking_html', 'options', "<div></div>");
        }

        // link intercompany invoice
        if (!frm.doc.__islocal && frm.doc.docstatus == 1 && (frm.doc.po_no || "").startsWith('SO-')) {
            has_intercompany_orders(frm).then(response => {
                if (response.message){
                    frm.dashboard.add_comment("Please also see " + response.message, 'green', true);
                }
            });
        }
    },
    company(frm) {
        set_naming_series(frm);                 // common function

        cache_company_key(frm);                 // prepare for company validation
    },
    before_save(frm) {
        set_income_accounts(frm);
        // set goodwill period to 5 days
        cur_frm.set_value("exclude_from_payment_reminder_until", frappe.datetime.add_days(frm.doc.due_date, 5));
    },
    is_return(frm) {
        prepare_naming_series(frm);
        setTimeout(() => { set_naming_series(frm); }, 1000);
    },
    posting_date(frm) {
        get_exchange_rate(frm);
    },
    validate(frm) {
        if (!locals.prevdoc_checked && frm.doc.__islocal) {
            frappe.msgprint( __("Please be patient, prices are being checked..."), __("Validation") );
            frappe.validated=false;
        }
        validate_credit_item_not_using_credits(frm);

        validate_company_references(frm);
    }
});


frappe.ui.form.on('Sales Invoice Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});


function has_intercompany_orders(frm) {
    return frappe.call({
        "method": "microsynth.microsynth.utils.has_intercompany_orders",
        "args": {
            "po_no": frm.doc.po_no || null
        }
    });
}


function clear_credits(frm) {
    cur_frm.clear_table("customer_credits");
    cur_frm.set_value("discount_amount", frm.doc.discount_amount - frm.doc.total_customer_credit);
    cur_frm.set_value("total_customer_credit", 0);
    cur_frm.set_value("remaining_customer_credit", 0);
    frappe.show_alert("Customer credits were cleared. Please check invoice and discount percentage before allocating customer credits again.");
}


function clone(frm) {
    frappe.call({
        'method': "microsynth.microsynth.utils.exact_copy_sales_invoice",
        'args': {
            'sales_invoice': frm.doc.name
        },
        'callback': function(r)
        {
            frappe.set_route("Form", "Sales Invoice", r.message)
        }
    });
}


function full_return(frm) {
    frappe.confirm('Are you sure you want to create a <b>submitted</b> Return / Credit Note against<br>' + frm.doc.name + '?',
    () => {
        frappe.call({
            'method': "microsynth.microsynth.credits.create_full_return",
            'args': {
                'sales_invoice': frm.doc.name
            },
            'freeze': true,
            'freeze_message': __("Creating full credit note..."), 
            'callback': function(r)
            {
                cur_frm.reload_doc();
                frappe.show_alert( __("A Return has been created. Please create a new Invoice.") );
            } 
        })
    }, () => {
        frappe.show_alert('Did not create a Return / Credit Note');
    });
}


function allocate_credits(frm) {
    if (!contains_credit_item(frm)) {
        frappe.call({
            'method': "microsynth.microsynth.credits.allocate_credits_to_invoice",
            'args': {
                'sales_invoice': frm.doc.name
            },
            'callback': function(r)
            {
                cur_frm.reload_doc();
                frappe.show_alert( __("allocated credits") );
            }
        });
    } else {
        frappe.msgprint( __("Please do not apply a customer credit to create a new customer credit"), __("Allocate credits") );
    }
}


function set_income_accounts(frm) {
    frappe.call({
        'method': "microsynth.microsynth.invoicing.get_income_accounts",
        'args': { 
            'customer': frm.doc.customer,
            'address': frm.doc.shipping_address_name || frm.doc.customer_address,
            'currency': frm.doc.currency,
            'sales_invoice_items': frm.doc.items
        },
        'async': false,
        'callback': function(r)
        {
            var income_accounts = r.message;
            for (var i = 0; i < cur_frm.doc.items.length; i++) {
                frappe.model.set_value("Sales Invoice Item", cur_frm.doc.items[i].name, "income_account", income_accounts[i]);
            }
        }
    });
}


function close_against_expense(frm) {
    frappe.prompt([
            {
                'fieldname': 'account', 
                'fieldtype': 'Link', 
                'label': __('Account'), 
                'options': 'Account',
                'reqd': 1,
                'get_query': function() { 
                    return { 
                        filters: {
                            'account_type': 'Expense Account',
                            'company': frm.doc.company
                        }
                    }
                },
                'description': __("Create a Journal Entry and close this receivable position against an expense account")
            }  
        ],
        function(values){
            frappe.call({
                'method': "microsynth.microsynth.credits.close_invoice_against_expense",
                'args': { 
                    'sales_invoice': frm.doc.name,
                    'account': values.account
                },
                'callback': function(r)
                {
                    cur_frm.reload_doc();
                }
            });
        },
        __('Close Invoice Against Expense Account'),
        __('OK')
    )
}


function get_exchange_rate(frm) {
    if (frm.doc.is_return === 0) {
        frappe.call({
            'method': 'erpnextswiss.erpnextswiss.finance.get_exchange_rate',
            'args': {
                'from_currency': frm.doc.currency,
                'company': frm.doc.company,
                'transaction_date': frm.doc.posting_date
            },
            'callback': function(response) {
                cur_frm.set_value("conversion_rate", response.message);
            }
        });
    }
}


function transmit_invoice(frm) {
    frappe.call({
        'method': 'microsynth.microsynth.invoicing.transmit_sales_invoice',
        'args': {
            'sales_invoice_id': frm.doc.name
        },
        'callback': function(response) {
            cur_frm.reload_doc();
        }
    });
}


// call zugferd to create and download xml
function download_zugferd_xml(frm) {
    var url = "/api/method/erpnextswiss.erpnextswiss.zugferd.zugferd.download_zugferd_xml"  
        + "?sales_invoice_name=" + encodeURIComponent(frm.doc.name);
    var w = window.open( frappe.urllib.get_full_url(url) );
    if (!w) {
        frappe.msgprint(__("Please enable pop-ups")); 
        return;
    }
}


function check_prevdoc_rates(frm) {
    var dn_details = [];
    if (frm.doc.items)
    {
        for (var i = 0; i < frm.doc.items.length; i++) {
            dn_details.push(frm.doc.items[i].dn_detail);
        }
        frappe.call({
            'method': 'microsynth.microsynth.utils.fetch_price_list_rates_from_prevdoc',
            'args': {
                'prevdoc_doctype': "Delivery Note",
                'prev_items': dn_details
            },
            'callback': function(response) {
                var prevdoc_price_list_rates = response.message;
                for (var i = 0; i < cur_frm.doc.items.length; i++) {
                    if(prevdoc_price_list_rates[i] != null) {
                        frappe.model.set_value(cur_frm.doc.items[i].doctype, cur_frm.doc.items[i].name, "price_list_rate", prevdoc_price_list_rates[i]);
                    }
                }
                locals.prevdoc_checked = true;
            }
        });
    } else {
        locals.prevdoc_checked = true;
    }
}


function open_mail_dialog(frm){
    if (frm.doc.docstatus != 1) {
        frappe.show_alert('Cannot email invoice because it is not submitted.');
    } else if (!frm.doc.invoice_to){
        frappe.show_alert('Please enter an Invoice To Contact with a valid email address before opening the mail dialog.');
    } else {
        frappe.call({
            'method': 'microsynth.microsynth.utils.get_email_ids',
            'args': {
                'contact': frm.doc.invoice_to
            },
            'callback': function(response) {
                if (response.message){
                    
                    new frappe.erpnextswiss.MailComposer({
                        'doc': cur_frm.doc,
                        'frm': cur_frm,
                        'subject': "Sales Invoice " + cur_frm.doc.name,
                        'recipients': response.message,
                        'cc': "info@microsynth.ch",
                        'attach_document_print': true,
                        'txt': "",
                        'check_all_attachments': false,
                        'replace_template': true
                    });
                    // note: once the mail is sent, a communication record is created and this will trigger setting the invoice_sent_on (see hooks.py, doc_events Communication on_insert)
                } else {
                    frappe.show_alert('Contact ' + frm.doc.invoice_to + ' has no email IDs. Please go to this Contact and add at least one email address.');
                }
            }
        });
    }
}

function validate_credit_item_not_using_credits(frm) {
    // this function checks that the customer credit item is not paid using a credit
    if ((!frm.doc.is_return) && (frm.doc.total_customer_credit > 0)) {
        // document is not a return and has a customer credit applied
        if (contains_credit_item(frm)) {
            // found a customer credit: not allowed!
            frappe.msgprint( __("Please do not apply a customer credit to create a new customer credit"), __("Validaton") );
            frappe.validated = false;
        }
    }
}

function validate_company_references(frm) {
    if (locals.company_key) {
        let suffix = " - " + locals.company_key;
        // verify income & expense accounts, cost center and warehouse
        if (frm.doc.items) {
            for (let i = 0; i < frm.doc.items.length; i++) {
                if ((frm.doc.items[i].income_account) && (!frm.doc.items[i].income_account.endsWith(suffix))) {
                    frappe.msgprint( __("Invalid income account: {0} does not belong to ").replace("{0}", frm.doc.items[i].income_account) + frm.doc.company, __("Company Validaton") );
                    frappe.validated = false;
                }
                if ((frm.doc.items[i].expense_account) && (!frm.doc.items[i].expense_account.endsWith(suffix))) {
                    frappe.msgprint( __("Invalid expense account: {0} does not belong to ").replace("{0}", frm.doc.items[i].expense_account) + frm.doc.company, __("Company Validaton") );
                    frappe.validated = false;
                }
                if ((frm.doc.items[i].cost_center) && (!frm.doc.items[i].cost_center.endsWith(suffix))) {
                    frappe.msgprint( __("Invalid cost center: {0} does not belong to ").replace("{0}", frm.doc.items[i].cost_center) + frm.doc.company, __("Company Validaton") );
                    frappe.validated = false;
                }
                if ((frm.doc.items[i].warehouse) && (!frm.doc.items[i].warehouse.endsWith(suffix))) {
                    frappe.msgprint( __("Invalid warehouse: {0} does not belong to ").replace("{0}", frm.doc.items[i].warehouse) + frm.doc.company, __("Company Validaton") );
                    frappe.validated = false;
                }
            }
        }

        // verify taxes and charges
        if ((frm.doc.taxes_and_charges) && (!frm.doc.taxes_and_charges.endsWith(suffix))) {
            frappe.msgprint( __("Invalid taxes and charges template: {0} does not belong to ").replace("{0}", frm.doc.taxes_and_charges) + frm.doc.company, __("Company Validaton") );
            frappe.validated = false;
        }
        if (frm.doc.taxes) {
            for (let i = 0; i < frm.doc.taxes.length; i++) {
                if (!frm.doc.taxes[i].account_head.endsWith(suffix)) {
                    frappe.msgprint( __("Invalid tax account: {0} does not belong to ").replace("{0}", frm.doc.taxes[i].account_head) + frm.doc.company, __("Company Validaton") );
                    frappe.validated = false;
                }
            }
        }
        // verify debtor
        if ((frm.doc.debit_to) && (!frm.doc.debit_to.endsWith(suffix))) {
            frappe.msgprint( __("Invalid debit to account {0}: does not belong to ").replace("{0}", frm.doc.debit_to) + frm.doc.company, __("Company Validaton") );
            frappe.validated = false;
        }
    } else {
        console.log("Company reference validation not possible: company key missing (this should not happen)");
    }
}

function contains_credit_item(frm) {
    for (var i = 0; i < (frm.doc.items || []).length; i++) {
        if (frm.doc.items[i].item_code === "6100") {
            return true;
        }
    }
    return false;
}

function create_accounting_note(frm) {
    if (cur_frm.is_dirty()) {
        frappe.msgprint( __("Please save your unsaved changes first."), __(Information) );
    } else {
        frappe.call({
            'method': 'microsynth.microsynth.report.accounting_note_overview.accounting_note_overview.create_accounting_note',
            'args': {
                'date': frappe.datetime.get_today(),
                'note': frm.doc.customer_name,
                'reference_doctype': frm.doc.doctype,
                'reference_name': frm.doc.name,
                'amount': frm.doc.grand_total,
                'account': frm.doc.debit_to,
                'currency': frm.doc.currency
            },
            'callback': function (r) {
                var doc = r.message;
                frappe.model.sync(doc);
                frappe.set_route("Form", doc.doctype, doc.name);
            }
        });
    }
}

function cache_company_key(frm) {
    if (frm.doc.company) {
        frappe.call({
            'method': "frappe.client.get",
            'args': {
                'doctype': 'Company',
                'name': frm.doc.company
            },
            'callback': function(r)
            {
                locals.company_key = r.message.abbr;
            }
        });
    }
}

function display_customer_credit_bookings(frm) {
    frappe.call({
        'method': 'microsynth.microsynth.credits.get_linked_customer_credit_bookings',
        'args': {
            'sales_invoice': frm.doc.name
        },
        'callback': function (r) {
            if (r.message) {
                let html = r.message.html;
                cur_frm.set_df_property('customer_credit_booking_html', 'options', html);
            } else {
                cur_frm.set_df_property('customer_credit_booking_html', 'options', "<div></div>");
            }
        }
    });
}
