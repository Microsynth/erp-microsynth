/* common functions */

// naming series automation
function prepare_naming_series(frm) {
    locals.naming_series_map = null;
    // cache naming series
    frappe.call({
        'method': 'microsynth.microsynth.naming_series.get_naming_series',
        'args': {
            'doctype': (frm.doc.doctype === "Sales Invoice" && frm.doc.is_return === 1) ? "Credit Note" : frm.doc.doctype
        },
        'callback': function (r) {
            locals.naming_series_map = r.message;
        }
    });
    if (!frm.doc.__islocal) {
        // lock company on saved records (prevent change due to naming series)
        cur_frm.set_df_property('company', 'read_only', 1);
    }
}

function set_naming_series(frm) {
    if (locals.naming_series_map) {
        cur_frm.set_value("naming_series", locals.naming_series_map[frm.doc.company]);
    } else {
        setTimeout(() => { set_naming_series(frm); }, 1000);
    }
}

// mark navbar in specific colour
window.onload = async function () {
    await sleep(1000);
    var navbars = document.getElementsByClassName("navbar");
    if (navbars.length > 0) {
        if (window.location.hostname.includes("erp-test") || (window.location.hostname.includes("localhost"))) {
            navbars[0].style.backgroundColor = "#e65023";
        }
    }
}

// access protection of the file manager
$(document).ready(function() {
    // access protection: user shall not go to the file manager
    if (!frappe.user.has_role("System Manager")) {
        if ((window.location.href.includes("/desk#List/File/")) || (window.location.href.includes("/desk#Form/File/"))) {
            window.location.replace("/desk");
        }
    }
    
    // disable stop_drop handler by default - i.e. on each access, potentially lingering stop_drops are disabled
    // window.removeEventListener("drop", stop_drop, true); // disabled because this trigger only works once and not on each document refresh
});

function sleep(milliseconds) {
   return new Promise(resolve => setTimeout(resolve, milliseconds));
}

// Set the taxes from the tax template 
/*function update_taxes(company, customer, address, category, date) {
    frappe.call({
        "method": "microsynth.microsynth.taxes.find_dated_tax_template",
        "args": {
            "company": company,
            "customer": customer,
            "shipping_address": address,
            "category": category,
            "date": date 
        },
        "async": false,
        "callback": function(response){
            var taxes = response.message;
            
            cur_frm.set_value("taxes_and_charges", taxes);

            frappe.call({
                "method":"frappe.client.get",
                "args": {
                    "doctype": "Sales Taxes and Charges Template",
                    "name": taxes
                },
                "async": false,
                "callback": function(response){
                    var tax_template = response.message;
                    cur_frm.clear_table("taxes");
                    for (var t = 0; t < tax_template.taxes.length; t++) {
                        var child = cur_frm.add_child('taxes')
                        
                        frappe.model.set_value(child.doctype, child.name, 'charge_type', tax_template.taxes[t].charge_type);
                        frappe.model.set_value(child.doctype, child.name, 'account_head', tax_template.taxes[t].account_head);
                        frappe.model.set_value(child.doctype, child.name, 'description', tax_template.taxes[t].description);
                        frappe.model.set_value(child.doctype, child.name, 'cost_center', tax_template.taxes[t].cost_center);
                        frappe.model.set_value(child.doctype, child.name, 'rate', tax_template.taxes[t].rate);
                    }
                }
            });
        }
    });
}*/


// hide chart buttons on reports
function hide_chart_buttons() {
    setTimeout(function() {
        frappe.query_report.page.remove_inner_button( __("Set Chart") );
        frappe.query_report.page.remove_inner_button( __("Hide Chart") );
    }, 500);
}

/* DEPRECATED, now in payment entry.js 
/// Avis booking
function allocate_avis(frm) {
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
                                var customer = this.grid_row.on_grid_fields[1];
                                var customer_name = this.grid_row.on_grid_fields[2];
                                var currency = this.grid_row.on_grid_fields[3];
                                var outstanding_amount = this.grid_row.on_grid_fields[4];
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
        primary_action: function(){
            var amount = recalc_allocation(d);
            d.hide();
            var v = d.get_values()
            // call backend to create the journal entry
            frappe.call({
                'method': "microsynth.microsynth.utils.book_avis",
                'args': {
                    'company': frm.doc.company,
                    'intermediate_account': account_matrix[frm.doc.company].unclear[v.currency],
                    'currency_deviation_account': account_matrix[frm.doc.company].currency,
                    'invoices': v.invoices,
                    'amount': amount,
                    'reference': frm.doc.name
               },
               callback: function(response) {
                    var jv = response.message;
                    cur_frm.set_value("remarks", cur_frm.doc.remarks + "\nAvis booked in " + jv);
                    // switch mode to transfer
                    var paid_to = cur_frm.doc.paid_to;
                    cur_frm.set_value("payment_type", "Internal Transfer");
                    setTimeout(function() {
                        cur_frm.set_value("paid_to", paid_to);
                        cur_frm.set_value("paid_from", account_matrix[frm.doc.company].unclear[v.currency])
                    }, 500);
               }
            });
        },
        primary_action_label: __('OK'),
        title: __('Allocate Avis')
    });
    d.show();

}

function recalc_allocation(d) {
    var sum = 0;
    for (var i = 0; i < d.fields[4].data.length; i++) {
        sum += d.fields[4].data[i].outstanding_amount;
    }
    let color = "black";
    if (sum != d.camt_amount) {
        color = "red";
    }
    d.set_value("allocated", "<span style='color: " + color + "; '>" + sum + "</span>");
    console.log("color: " + color);
    return sum
}
*/ 

function hide_in_words() {
    // remove in words (because customisation and setting both do not apply)
    cur_frm.set_df_property('in_words', 'hidden', 1);
    cur_frm.set_df_property('base_in_words', 'hidden', 1);
    // this all does not work on base_in_words :-( last resort
    $("[data-fieldname='base_in_words']").hide();
}

// access protection: disable removing attachments
function access_protection() {
    // disable all attachments
    var styleSheet = document.createElement("style");
    styleSheet.innerText = ".attachment-row .close { display: none !important; }";
    document.head.appendChild(styleSheet);
}

// this function voids the above access protection
function remove_access_protection() {
    $('style').remove();
}

// QM Documents: remove action button for list and report to prevent illegal actions
if (window.location.href.includes("/desk#List/QM%20Document/")) {
    var css = ".btn-primary.dropdown-toggle { display: none; }";
    var head = document.head || document.getElementsByTagName('head')[0];
    var style = document.createElement('style');
    head.appendChild(style);
    style.type = 'text/css';
    style.appendChild(document.createTextNode(css));
}

function force_cancel(dt, dn) {
    frappe.confirm(
        __("Are you sure that you want to set this draft directly to the cancelled state?"),
        function () {
            // yes
            frappe.call({
                'method': 'microsynth.microsynth.utils.force_cancel',
                'args': {
                    'dt': dt,
                    'dn': dn
                },
                callback: function(r){
                    cur_frm.reload_doc();
                }
            });
        },
        function () {
            // no: do nothing
        }
    );
}

// Add the clear button. Call this function in the onload trigger of doctype_list.js
function add_clear_button() {
    var filter_bar = document.getElementsByClassName("page-form");
    var btn_clear = document.createElement("div");
    btn_clear.setAttribute('class', 'form-group frappe-control input-max-width col-md-2');
    btn_clear.innerHTML = "<button id='btn_clear' class='btn text-muted'>Clear</button>";
    for (var i = 0; i < filter_bar.length; i++) {
        filter_bar[i].appendChild(btn_clear);
        document.getElementById("btn_clear").onclick = clear_filters;
    }
}

// this is embedded in doctype_list.js functions to clear all filters
function clear_filters() {
    var standard_filters = {};
    var fields = frappe.meta.docfield_list[cur_list.meta.name];
    for (var i = 0; i < fields.length; i++) {
        if (fields[i].in_standard_filter === 1) {
            standard_filters[fields[i].fieldname] = '';
        }
    }
    frappe.set_route("List", cur_list.meta.name, standard_filters);
}

function fetch_accounting_notes(frm) {
    frappe.call({
        'method': 'microsynth.microsynth.doctype.accounting_note.accounting_note.get_accounting_notes_html',
        'args': {
            'reference_name': frm.doc.name
        },
        'callback': function (response) {
            frm.dashboard.add_comment(response.message, 'yellow', true);
        }
    });
}

// this is a handler function that prevents anything from being dropped on a form
function stop_drop(event) {
    event.stopImmediatePropagation();
}
