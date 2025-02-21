/* this script requires locals.account_matrix and locals.cost_center_matrix */
/* Custom script extension for Payment Entry */
frappe.ui.form.on('Payment Entry', {
    refresh(frm) {
        check_display_unallocated_warning(frm);

        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Create Accounting Note"), function() {
                create_accounting_note(frm);
            });
        }

        /* add auto deduction buttons */
        if (frm.doc.docstatus === 0) {

            frm.add_custom_button(__("Aufwand"), function() {
                quick_expense(frm);
            }).addClass("btn-danger");
            
            frm.add_custom_button(__("Abklärungskonto"), function() {
                deduct_to_unclear(frm);
            }, __("Ausbuchen"));
            frm.add_custom_button(__("Spesen des Geldverkehrs"), function() {
                bank_expenses(frm);
            }, __("Ausbuchen"));
            frm.add_custom_button(__("Kursdifferenzen"), function() {
                currency(frm);
            }, __("Ausbuchen"));
            frm.add_custom_button(__("Löhne"), function() {
                salaries(frm);
            }, __("Ausbuchen"));
            frm.add_custom_button(__("Aufwand"), function() {
                expense(frm);
            }, __("Ausbuchen"));
            frm.add_custom_button(__("Umsatzsteuerabzug"), function() {
                special(frm);
            }, __("Ausbuchen"));
            frm.add_custom_button(__("Intracompany BAL-WIE"), function() {
                intracompany(frm);
            }, __("Ausbuchen"));
            
            frm.add_custom_button(__("Voll zuweisen"), function() {
                match_outstanding_amounts();
            });
            
            frm.add_custom_button(__("Avis verbuchen"), function() {
                allocate_avis(frm);
            });
            
            // check currency
            if (frm.doc.company === "Microsynth AG") {
                if ((["EUR", "USD"].includes(frm.doc.paid_from_account_currency)) && (frm.doc.source_exchange_rate === 1)) {
                    get_exchange_rate(frm);
                }
            }
        }
        
        /* filter: only show invoices with outstanding amount (#14045) */
        frm.fields_dict.references.grid.get_field('reference_name').get_query =
          function() {
            return {
                    filters: [
                        ["outstanding_amount", "!=", "0"],
                        ["docstatus", "=", 1],
                        [frm.doc.party_type.toLowerCase(), "=", frm.doc.party],
                        ["company", "=", frm.doc.company]
                ]
            };
          };
        
        if (!frm.doc.__islocal) {
            fetch_accounting_notes(frm);
        }
    },
    unallocated_amount(frm) {
        check_display_unallocated_warning(frm);
    },
    difference_amount(frm) {
        check_display_unallocated_warning(frm);
    },
    validate: function(frm) {
        if (frm.doc.references) {
            for (var i= 0; i < frm.doc.references.length; i++) {
                if (frm.doc.references[i].outstanding_amount > frm.doc.references[i].allocated_amount) {
                    frappe.msgprint( __("Warning, Outstanding > Allocated in row " + (i+1) + ".", __("Validation") ));
                    break;
                }
            }
        }
    },
    before_save: function(frm) {
        // hotfix: check for < 0.01 allocations
        if ((frm.doc.references) && (frm.doc.references.length > 0)) {
            for (var i = 0; i < frm.doc.references.length; i++) {
                var delta = Math.abs(frm.doc.references[i].outstanding_amount - frm.doc.references[i].allocated_amount);
                console.log(i + ": delta=" + delta);
                if ((delta < 0.01) && (delta > 0)) {
                    frappe.model.set_value(frm.doc.references[i].doctype, frm.doc.references[i].name, 'allocated_amount', frm.doc.references[i].outstanding_amount);
                }
            }
        }
    },
    paid_amount: function(frm) {
        /* check and assert camt amount */
        if ((frm.doc.camt_amount) && (frm.doc.ignore_camt === 0) && (frm.doc.paid_amount != frm.doc.camt_amount)) {
            frm.set_value("paid_amount", frm.doc.camt_amount);
        }
    }
});


function check_display_unallocated_warning(frm) {
    if (Math.round(100 * Math.abs(cur_frm.doc.unallocated_amount || cur_frm.doc.difference_amount || 0)) > 0) {
        cur_frm.dashboard.clear_comment();
        cur_frm.dashboard.add_comment(__('This document has an unallocated amount.'), 'red', true);
    } else {
        cur_frm.dashboard.clear_comment();
    }
}


function create_accounting_note(frm) {
    if (cur_frm.is_dirty()) {
        frappe.msgprint( __("Please save your unsaved changes first."), __(Information) );
    } else {
        if (frm.doc.payment_type == "Receive") {
            var account = frm.doc.paid_to;
            var currency = frm.doc.paid_to_account_currency;
        } else if (frm.doc.payment_type == "Pay") {
            var account = frm.doc.paid_from;
            var currency = frm.doc.paid_from_account_currency;
        } else if (frm.doc.payment_type == "Internal Transfer") {
            var account = frm.doc.paid_to;
            var currency = frm.doc.paid_to_account_currency;
        } else {
            console.log("Payment Type = '" + frm.doc.payment_type + "'");
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __("Unknown Payment Type '" + frm.doc.payment_type + "'. Please contact 5.3.2 IT Applications.")
            });
            return;
        }
        frappe.call({
            'method': 'microsynth.microsynth.report.accounting_note_overview.accounting_note_overview.create_accounting_note',
            'args': {
                'date': frm.doc.posting_date,
                'note': frm.doc.party_name ? frm.doc.party_name : "",  // empty string as fallback if party_name does not exists
                'reference_doctype': frm.doc.doctype,
                'reference_name': frm.doc.name,
                'amount': frm.doc.paid_amount,
                'account': account,
                'currency': currency
            },
            'callback': function (r) {
                var doc = r.message;
                frappe.model.sync(doc);
                frappe.set_route("Form", doc.doctype, doc.name);
            }
        });
    }
}

/* Abklärundskonto */
function deduct_to_unclear(frm) {
    var amount = 0;
    if (frm.doc.payment_type === "Pay") {
        amount = (frm.doc.unallocated_amount) || frm.doc.difference_amount;
    } else {
        amount = ((-1) * frm.doc.unallocated_amount) || frm.doc.difference_amount;
    }
    add_deduction(locals.account_matrix[frm.doc.company].unclear[frm.doc.paid_to_account_currency], locals.cost_center_matrix[frm.doc.company], amount);
}

/* in den Aufwand buchen (aktuell keine Kreditoren) */
function expense(frm) {
    var amount = 0;
    if (frm.doc.payment_type === "Pay") {
        if ((frm.doc.source_exchange_rate != 1) && ((!frm.doc.references) || (frm.doc.references.length == 0))) {
            amount = frm.doc.base_paid_amount;   // use full paid amount, with valuation
        } else {
            amount = (frm.doc.unallocated_amount) || frm.doc.difference_amount;
        }
    } else {
        amount = ((-1) * frm.doc.unallocated_amount) || frm.doc.difference_amount;
    }
    add_deduction(locals.account_matrix[frm.doc.company].expense, locals.cost_center_matrix[frm.doc.company], amount);
}

function quick_expense(frm) {
    frappe.call({
        'method':"microsynth.microsynth.utils.deduct_and_close",
        'args':{
            'payment_entry': frm.doc.name,
            'account': locals.account_matrix[frm.doc.company].expense,
            'cost_center': locals.cost_center_matrix[frm.doc.company]
        },
        'callback': function(response) {
            window.close();
        }
    });
}

/* Löhne (aktuell ohne HR direkt in den HR-Aufwand) */
function salaries(frm) {
    var amount = 0;
    if (frm.doc.payment_type === "Pay") {
        amount = (frm.doc.unallocated_amount) || frm.doc.difference_amount;
    } else {
        amount = ((-1) * frm.doc.unallocated_amount) || frm.doc.difference_amount;
    }
    add_deduction(locals.account_matrix[frm.doc.company].salaries, locals.cost_center_matrix[frm.doc.company], amount);
}

/* Bankspesen */
function bank_expenses(frm) {
    var amount = 0;
    if (frm.doc.payment_type === "Pay") {
        amount = (frm.doc.unallocated_amount) || frm.doc.difference_amount;
    } else {
        amount = ((-1) * frm.doc.unallocated_amount) || frm.doc.difference_amount;
    }
    add_deduction(locals.account_matrix[frm.doc.company].bank, locals.cost_center_matrix[frm.doc.company], amount);
}

/* Währungen */
function currency(frm) {
    var amount = 0;
    if (frm.doc.payment_type === "Pay") {
        amount = (frm.doc.unallocated_amount) || frm.doc.difference_amount;
    } else {
        amount = ((-1) * frm.doc.unallocated_amount) || frm.doc.difference_amount;
    }
    add_deduction(locals.account_matrix[frm.doc.company].currency, locals.cost_center_matrix[frm.doc.company], amount);
}

/* Spezialfall */
function special(frm) {
    var amount = 0;
    if (frm.doc.payment_type === "Pay") {
        amount = (frm.doc.unallocated_amount) || frm.doc.difference_amount;
    } else {
        amount = ((-1) * frm.doc.unallocated_amount) || frm.doc.difference_amount;
    }
    add_deduction(locals.account_matrix[frm.doc.company].special, locals.cost_center_matrix[frm.doc.company], amount);
}

/* Intracompany: BAL - WIE */
function intracompany(frm) {
    if (frm.doc.company === "Microsynth AG") {
        if (frm.doc.payment_type === "Receive") {
            // EUR for WIE received in BAL
            cur_frm.set_value("payment_type", "Internal Transfer");
            cur_frm.set_value("paid_from", locals.account_matrix[frm.doc.company].intracompany.WIE);
            cur_frm.set_value("paid_to", locals.account_matrix[frm.doc.company].intracompany.BAL);
        } else {
            // EUR sent to WIE
            cur_frm.set_value("payment_type", "Internal Transfer");
            cur_frm.set_value("paid_to", locals.account_matrix[frm.doc.company].intracompany.WIE);
            cur_frm.set_value("paid_from", locals.account_matrix[frm.doc.company].intracompany.BAL);
        }
    } else if (frm.doc.company === "Microsynth Austria GmbH") {
        if (frm.doc.camt_amount === 0) {
            // close debtor (payment to BAL)
            add_deduction(locals.account_matrix[frm.doc.company].intracompany.BAL, locals.cost_center_matrix[frm.doc.company], frm.doc.unallocated_amount);
        } else {
            // EUR for WIE received from BAL
            add_deduction(locals.account_matrix[frm.doc.company].intracompany.BAL, locals.cost_center_matrix[frm.doc.company], ((-1) * frm.doc.unallocated_amount));
        }
    }
}

function add_deduction(account, cost_center, amount) {
    var child = cur_frm.add_child('deductions');
    frappe.model.set_value(child.doctype, child.name, 'account', account);
    frappe.model.set_value(child.doctype, child.name, 'cost_center', cost_center);
    frappe.model.set_value(child.doctype, child.name, 'amount', amount);
}

function round_currency(value) {
    return (Math.round(value * 100) / 100);
}

function get_exchange_rate(frm) {
    frappe.call({
        'method':"frappe.client.get_list",
        'args':{
            'doctype':"Currency Exchange",
            'filters': [
                ["from_currency","=", frm.doc.paid_from_account_currency],
                ["date", "<=", frm.doc.posting_date]
            ],
            'fields': ["exchange_rate"]
        },
        'callback': function(response) {
            cur_frm.set_value("source_exchange_rate", response.message[0].exchange_rate);
            cur_frm.set_value("target_exchange_rate", response.message[0].exchange_rate);
        }
    });
}

function match_outstanding_amounts() {
    (cur_frm.doc.references || []).forEach(function (reference) {
        frappe.model.set_value(reference.doctype, reference.name, 'allocated_amount', reference.outstanding_amount);
    });
    cur_frm.refresh_fields();
}

/// Avis booking
function allocate_avis(frm) {
    // hack: disable delete rows
    var styles = ".grid-delete-row { display: none; } .grid-remove-rows { display: none; } .row-actions { display: none !important; }";
    var styleSheet = document.createElement("style");
    styleSheet.innerText = styles;
    document.head.appendChild(styleSheet);
    
    var d = new frappe.ui.Dialog({
        'fields': [
            {
                'fieldname': 'camt_amount', 
                'fieldtype': 'Float', 
                'label': __('Amount'), 
                'default': frm.doc.camt_amount,
                'precision': 2,
                'read_only': 1
            },
            {
                'fieldname': 'col_1', 
                'fieldtype': 'Column Break'
            },
            {
                'fieldname': 'currency', 
                'fieldtype': 'Data', 
                'label': __('Currency'), 
                'default': frm.doc.paid_to_account_currency,
                'read_only': 1
            },
            {
                'fieldname': 'sec_1', 
                'fieldtype': 'Section Break', 
                'label': __('Allocation')
            },
            {
                'fieldname': 'invoices', 
                'fieldtype': 'Table', 
                'label': __('Invoices'), 
                'reqd': 1,
                'fields' : [
                    {
                        'fieldname': 'sales_invoice', 
                        'fieldtype': 'Link', 
                        'label': __('Sales Invoice'),
                        'options': "Sales Invoice",
                        'in_list_view': 1,
                        'reqd': 1,
                        'change': function() {
                            if (this.get_value()) {
                                var customer = this.grid_row.on_grid_fields_dict.customer;
                                var customer_name = this.grid_row.on_grid_fields_dict.customer_name;
                                var currency = this.grid_row.on_grid_fields_dict.currency;
                                var outstanding_amount = this.grid_row.on_grid_fields_dict.outstanding_amount;
                                frappe.call({
                                    'method': "frappe.client.get",
                                    'args': {
                                        "doctype": "Sales Invoice",
                                        "name": this.get_value()
                                    },
                                    'callback': function(r)
                                    {
                                        var sinv = r.message;
                                        customer.set_value(sinv.customer);
                                        customer_name.set_value(sinv.customer_name);
                                        currency.set_value(sinv.currency);
                                        outstanding_amount.set_value(sinv.outstanding_amount);
                                        
                                        recalc_allocation(d);
                                    }
                                });
                            }
                        },
                        get_query: function() {
                            return {
                                'filters': [ 
                                    ['company', '=', frm.doc.company],
                                    ['outstanding_amount', '>', 0],
                                    ['currency', '=', frm.doc.paid_to_account_currency]
                                ]
                            };
                        }
                    },
                    {
                        'fieldname': 'customer', 
                        'fieldtype': 'Data', 
                        'label': __('Customer'),
                        'in_list_view': 1,
                        'read_only': 1
                    },
                    {
                        'fieldname': 'customer_name', 
                        'fieldtype': 'Data', 
                        'label': __('Customer Name'),
                        'in_list_view': 1,
                        'read_only': 1
                    },
                    {
                        'fieldname': 'currency', 
                        'fieldtype': 'Data', 
                        'label': __('Currency'),
                        'in_list_view': 1,
                        'read_only': 1
                    },
                    {
                        'fieldname': 'outstanding_amount', 
                        'fieldtype': 'Float', 
                        'precision': 2,
                        'label': __('Outstanding Amount'),
                        'in_list_view': 1,
                        'read_only': 1
                    }
                ],
                'data': [],
                'get_data': () => {
                    return [];
                }
            },
            {
                'fieldname': 'button_clear_last', 
                'fieldtype': 'Button', 
                'label': __('Remove Last Row'),
                'click': function() {
                    var idx =  d.fields_dict.invoices.grid.grid_rows.length;
                    delete_row_in_childtbl("invoices", idx);
                }
            },
            {
                'fieldname': 'sec_1', 
                'fieldtype': 'Section Break', 
                'label': __('Sum')
            },
            {
                'fieldname': 'allocated', 
                'fieldtype': 'Data',
                'label': __('Allocated'),
                'default': 0,
                'read_only': 1
            },
        ],
        'primary_action': function(){
            var amount = recalc_allocation(d);
            var v = d.get_values();
            // verify that no transaction appears twice
            var has_duplicates = false;
            var invoices = [];
            for (var i = 0; i < v.invoices.length; i++) {
                if (invoices.includes(v.invoices[i].sales_invoice)) {
                    has_duplicates = true;
                    frappe.msgprint( __("Warning: {0} appears more than once.").replace("{0}", v.invoices[i].sales_invoice), __("Validation") );
                    continue;
                } else {
                    invoices.push(v.invoices[i].sales_invoice);
                }
            }
            if (!has_duplicates) {
                // reset styles
                try { document.head.removeChild(styleSheet); } catch {}
                d.hide();
                // call backend to create the journal entry
                frappe.call({
                    'method': "microsynth.microsynth.utils.book_avis",
                    'args': {
                        'company': frm.doc.company,
                        'intermediate_account': locals.account_matrix[frm.doc.company].unclear[v.currency],
                        'currency_deviation_account': locals.account_matrix[frm.doc.company].currency,
                        'invoices': v.invoices,
                        'amount': amount,
                        'reference': frm.doc.name,
                        'date': frm.doc.posting_date
                   },
                   callback: function(response) {
                        var jv = response.message;
                        cur_frm.set_value("remarks", cur_frm.doc.remarks + "\nAvis booked in " + jv);
                        // switch mode to transfer
                        var paid_to = cur_frm.doc.paid_to;
                        cur_frm.set_value("payment_type", "Internal Transfer");
                        setTimeout(function() {
                            cur_frm.set_value("paid_to", paid_to);
                            cur_frm.set_value("paid_from", locals.account_matrix[frm.doc.company].unclear[v.currency])
                            // 2024-05-30: automatic save to prevent unsaved PE
                            cur_frm.save();
                        }, 500);
                   }
                });
            }
        },
        'primary_action_label': __('OK'),
        'title': __('Allocate Avis'),
        'secondary_action': function() {
            /* reset styles */
            try { document.head.removeChild(styleSheet); } catch {}
        }
    });
    d.show();

    setTimeout(function () {
        var modals = document.getElementsByClassName("modal-dialog");
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = "1000px";
        }
    }, 300);
}

function recalc_allocation(d) {
    let sum = 0;
    for (let i = 0; i < d.fields[4].data.length; i++) {
        sum += (d.fields[4].data[i].outstanding_amount || 0);
    }
    let color = "black";
    if (sum.toFixed(2) != (d.fields_dict.camt_amount.value || 0).toFixed(2)) {
        color = "red";
    }
    d.set_value("allocated", "<span style='color: " + color + "; '>" + sum.toLocaleString("de-ch", {minimumFractionDigits: 2, maximumFractionDigits: 2}) + "</span>");
    return sum
}

function delete_row_in_childtbl(table, idx) {
    var tasks = [];
    
    tasks.push(() => {
        cur_dialog.fields_dict[table].grid.df.data = cur_dialog.fields_dict[table].grid.get_data();
        cur_dialog.fields_dict[table].grid.df.data = cur_dialog.fields_dict[table].grid.df.data.filter((row)=> row.idx != idx);
        cur_dialog.fields_dict[table].grid.grid_rows[idx-1].remove();
    });
    
    tasks.push(() => {
        cur_dialog.fields_dict[table].grid.df.data.forEach((row, index) => row.idx = index + 1);
    });
    
    tasks.push(() => {
        cur_dialog.fields_dict[table].grid.refresh()
    });

    frappe.run_serially(tasks);
}
