/* Custom script extension for Sales Invoice */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Reference"),
        'items': ["Payment Reminder"]
    }
]);


frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        locals.prevdoc_checked = false;
        prepare_naming_series(frm);             // common function

        // remove Menu > Email if document is not valid
        if (frm.doc.docstatus != 1) {
            var target ="span[data-label='" + __("Email") + "']";
            $(target).parent().parent().remove();
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
    },
    company(frm) {
        set_naming_series(frm);                 // common function
    },
    on_submit(frm) {
        if (frm.doc.total_customer_credit > 0) {
            book_credits(frm.doc.name);
        }
    },
    before_cancel(frm) {
        if (frm.doc.total_customer_credit > 0) {
            cancel_credit_journal_entry(frm.doc.name)
        }
    },
    before_save(frm) {
        set_income_accounts(frm);
        // set goodwill period to 10 days
        cur_frm.set_value("exclude_from_payment_reminder_until", frappe.datetime.add_days(frm.doc.due_date, 10));
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
    }
});


frappe.ui.form.on('Sales Invoice Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});


function clear_credits(frm) {
    frm.doc.customer_credits = [];
    frm.doc.discount_amount = frm.doc.discount_amount - frm.doc.total_customer_credit;
    frm.doc.total_customer_credit = 0;
    frm.doc.remaining_customer_credit = 0;
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


function allocate_credits(frm) {
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
}


function book_credits(sales_invoice) {
    frappe.call({
        'method': "microsynth.microsynth.credits.book_credit",
        'args': { 
            'sales_invoice': sales_invoice 
        },
        'callback': function(r)
        {
            frappe.show_alert( __("booked credits"));
        }
    });
}


function set_income_accounts(frm) {
    frappe.call({
        'method': "microsynth.microsynth.invoicing.get_income_accounts",
        'args': { 
            'address': frm.doc.shipping_address_name || frm.doc.customer_address,
            'currency': frm.doc.currency,
            'sales_invoice_items': frm.doc.items
        },
        'async': false,
        'callback': function(r)
        {
            var income_accounts = r.message;
            //console.log(income_accounts);
            for (var i = 0; i < cur_frm.doc.items.length; i++) {
                frappe.model.set_value("Sales Invoice Item", cur_frm.doc.items[i].name, "income_account", income_accounts[i]);
            }
        }
    });
}


function cancel_credit_journal_entry(sales_invoice) {
    frappe.call({
        'method': "microsynth.microsynth.credits.cancel_credit_journal_entry",
        'args': { 
            'sales_invoice': sales_invoice 
        },
        'callback': function(r)
        {
            frappe.show_alert( __("cancelled " + r.message));
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
