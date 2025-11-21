/* Custom script extension for Sales Order */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Fulfillment"),
        'items': ["Tracking Code"]
    }
]);


/* Custom script extension for Sales Order */
frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        // allow Accounts Manager to add Web Order ID if not yet set
        if (frm.doc.docstatus == 1 && !frm.doc.web_order_id && frappe.user.has_role("Accounts Manager")) {
            cur_frm.set_df_property('web_order_id', 'read_only', false);
        } else if (frm.doc.docstatus > 0) {
            cur_frm.set_df_property('web_order_id', 'read_only', true);
        }
        // remove Menu > Email if document is not valid
        if (frm.doc.docstatus != 1) {
            var target ="span[data-label='" + __("Email") + "']";
            $(target).parent().parent().remove();
        }

        if (!frm.doc.product_type && cur_frm.doc.docstatus == 0 && !frm.doc.__islocal) {
            frappe.msgprint( __("Please set a Product Type"), __("Validation") );
        }

        // link intercompany order
        if (!frm.doc.__islocal && frm.doc.docstatus == 1) {
            has_intercompany_order(frm).then(response => {
                if (response.message){
                    frm.dashboard.add_comment("Please also see <a href='/desk#Form/Sales Order/" + response.message + "'>" + response.message + "</a>", 'green', true);
                }
            });
        }

        // emphasize the usage of a manually created Customer
        if (!frm.doc.__islocal && frm.doc.docstatus == 0 && !(/^\d+$/.test(frm.doc.customer))) {
            cur_frm.dashboard.clear_comment();
            frm.dashboard.add_comment( __("Are you sure to continue with a <b>manually created Customer</b>? Please check to change for a Customer created by the webshop with a numeric ID."), 'red', true);
        }

        if (!frm.doc.__islocal && frm.doc.docstatus == 1) {
            frm.add_custom_button(__("Print Delivery Label"), function() {
                frappe.call({
                    "method": "microsynth.microsynth.labels.print_shipping_label",
                    "args": {
                        "sales_order_id": frm.doc.name
                    }
                });
            });
        } else {
            prepare_naming_series(frm);             // common function
        }

        // show a warning if is_punchout
        if (frm.doc.docstatus == 0 && frm.doc.is_punchout == 1) {
            frm.dashboard.add_comment( __("Punchout Order! Please do <b>not</b> edit the Items."), 'red', true);
        }

        if (frm.doc.is_punchout == 1 && frm.doc.docstatus == 1 && !frappe.user.has_role("System Manager")) {
            cur_frm.set_df_property('po_no', 'read_only', 1);
        }

        if (frm.doc.customer && frm.doc.product_type && frm.doc.docstatus == 0) {
            // Call a python function that checks if the Customer has a Distributor for the Product Type
            frappe.call({
                'method': "microsynth.microsynth.utils.has_distributor",
                'args': {
                    "customer": frm.doc.customer,
                    "product_type": frm.doc.product_type
                },
                'callback': function(response) {
                    if (response.message) {
                        cur_frm.dashboard.clear_comment();
                        cur_frm.dashboard.add_comment('Customer <b>' + cur_frm.doc.customer + '</b> has a Distributor for Product Type <b>' + cur_frm.doc.product_type + '</b>. Please ask the administration how to create this Sales Order correctly <b>before</b> submitting it.', 'red', true);
                    }
                }
            });
        }

        // if (frm.doc.docstatus === 2 && frm.doc.web_order_id) {
        //     frm.add_custom_button(__("Search valid version"), function() {
        //         frappe.set_route("List", "Sales Order", {"web_order_id": frm.doc.web_order_id, "docstatus": 1});
        //     });
        // }
        if (!frm.doc.__islocal) {
            frm.add_custom_button("Related Documents", function () {
                if (frm.doc.web_order_id) {
                    frappe.set_route("query-report", "Sales Document Overview", {
                        "web_order_id": frm.doc.web_order_id
                    });
                } else {
                    frappe.set_route("query-report", "Sales Document Overview", {
                        "document_id": frm.doc.name
                    });
                }
            }, __("View"));
        }

        if (frm.doc.docstatus == 1) {
            if (!frm.doc.customer_address) {
                frappe.msgprint({
                    title: __('Missing Billing Address'),
                    indicator: 'red',
                    message: __("Please enter and save a <b>Billing Address Name</b> in the section <b>Address and Contact</b>.")
                });
            }
            if (!frm.doc.shipping_address_name) {
                frappe.msgprint({
                    title: __('Missing Shipping Address'),
                    indicator: 'red',
                    message: __("Please enter and save a <b>Shipping Address Name</b> in the section <b>Address and Contact</b>.")
                });
            }
        }

        hide_in_words();

        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            });
        }

        if ((!frm.doc.__islocal) && frm.doc.docstatus < 2) {
            frm.add_custom_button(__("Link Quotation"), function() {
                link_quote(cur_frm.doc.name);
            });
        }

        // Show button only in Draft with empty customer_credits table
        if (frm.doc.docstatus === 0 && (!frm.doc.credit_accounts || frm.doc.credit_accounts.length === 0)) {
            frm.add_custom_button(__('Add Credit Accounts'), function () {
                show_credit_account_dialog(frm);
            });
        }
    },
    before_save(frm) {
        /*if (frm.doc.product_type == "Oligos" || frm.doc.product_type == "Material") {
            var category = "Material";
        } else {
            var category = "Service";
        };
        if (frm.doc.oligos != null && frm.doc.oligos.length > 0 ) {
            category = "Material";
        };  */
        // update taxes was moved to the server-side trigger (see hooks.py)
        //update_taxes(frm.doc.company, frm.doc.customer, frm.doc.shipping_address_name, category, frm.doc.delivery_date);
    },
    validate(frm) {
        // block Product Type NGS
        if (frm.doc.product_type === "NGS") {
            frappe.throw(__("Product Type NGS is deprecated. Please use Genetic Analysis instead."))
        }
    },
    before_submit(frm) {
        // Check if contact_person is set
        if (frm.doc.contact_person) {
            // Prevent automatic submission while we wait for confirmation
            frappe.validated = false;
            frappe.call({
                'method': 'frappe.client.get_value',
                'args': {
                    'doctype': 'Contact',
                    'filters': { name: frm.doc.contact_person },
                    'fieldname': 'has_webshop_account'
                },
                'async': false,
                'callback': function(r) {
                    if (r.message && r.message.has_webshop_account === 0) {
                        const escaped_contact = frappe.utils.escape_html(frm.doc.contact_person);
                        const message = `<b>No Webshop Account</b> found for Contact Person <code>${escaped_contact}</code>.<br>
                            A Webshop Account is strongly recommended.<br><br>
                            Do you want to abort submission and select a Contact Person with a Webshop Account in the section 'Address and Contact'?<br>
                            Click No to continue at your own risk.`;
                        // Show confirmation dialog if no webshop account
                        frappe.confirm(message,
                            function () {
                                frappe.msgprint("Submission cancelled. Please select a Contact Person with a Webshop Account.");
                            },
                            function () {
                                frappe.validated = true;
                                frm.save('Submit');
                            }
                        );
                    } else {
                        // Contact has a webshop account → allow submission
                        frappe.validated = true;
                    }
                }
            });
        }
        // TODO: Check how it interfers with the confirm above:
        return new Promise(resolve => {
            // If already has credit accounts -> allow submission
            if (frm.doc.credit_accounts && frm.doc.credit_accounts.length > 0) {
                resolve();
                return;
            }
            // Otherwise fetch available accounts
            frappe.call({
                'method': "microsynth.microsynth.credits.get_available_credit_accounts",
                'args': {
                    'company': frm.doc.company,
                    'currency': frm.doc.currency,
                    'customer': frm.doc.customer,
                    'product_types': frm.doc.product_type ? [frm.doc.product_type] : []
                },
                'callback': function (r) {
                    if (r.exc) {
                        resolve();
                        return;
                    }
                    const accounts = r.message || [];

                    if (accounts.length === 0) {
                        // No available credit accounts -> submit
                        resolve();
                        return;
                    }
                    // Ask confirm #1
                    frappe.confirm(
                        __("Do you want this order to be deducted from the following Credit Account(s)?")
                        + "<br><br>" + render_accounts_table(accounts),
                        function yes() {
                            // Add accounts automatically -> then submit
                            add_accounts_to_sales_order(frm, accounts);
                            frm.save().then(() => resolve());
                        },
                        function no() {
                            // Ask confirm #2
                            frappe.confirm(
                                __("Do you want to apply Credit Accounts manually using the button 'Add Credit Accounts'?"),
                                function yes_manual() {
                                    // stop submit
                                    resolve(false);
                                    // TODO: Why is it submitted anyway?
                                },
                                function no_just_submit() {
                                    // submit anyway
                                    resolve();
                                }
                            );
                        }
                    );
                }
            });
        });
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
    }
});

frappe.ui.form.on('Sales Order Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});


function has_intercompany_order(frm) {
    return frappe.call({
        "method": "microsynth.microsynth.utils.has_intercompany_order",
        "args": {
            "sales_order_id": frm.doc.name,
            "po_no": frm.doc.po_no || null
        }
    });
}


function link_quote(sales_order) {
    if (cur_frm.doc.docstatus == 0) {
        var d = new frappe.ui.Dialog({
            'fields': [
                {'fieldname': 'sales_order', 'fieldtype': 'Link', 'options': "Sales Order", 'label': __('Sales Order'), 'read_only': 1, 'default': sales_order},
                {'fieldname': 'quotation', 'fieldtype': 'Link', 'options': "Quotation", 'label': __('Quotation'), 'reqd': 1}
            ],
            'primary_action': function(){
                d.hide();
                var values = d.get_values();
                frappe.call({
                    'method': "microsynth.microsynth.quotation.link_quotation_to_order",
                    'args':{
                        'sales_order': values.sales_order,
                        'quotation': values.quotation
                    },
                    'callback': function(r) {
                        if (r.message) {
                            cur_frm.reload_doc();
                            frappe.show_alert("Successfully linked Quotation");
                        } else {
                            frappe.show_alert("Internal Error")
                        }
                    }
                });
            },
            'primary_action_label': __('Link Quote & pull its rates'),
            'title': __('Link quote to Sales Order & pull quote rates')
        });
        d.show();
    }
    else if (cur_frm.doc.docstatus == 1) {
        var d = new frappe.ui.Dialog({
            'fields': [
                {'fieldname': 'sales_order', 'fieldtype': 'Link', 'options': "Sales Order", 'label': __('Sales Order'), 'read_only': 1, 'default': sales_order},
                {'fieldname': 'quotation', 'fieldtype': 'Link', 'options': "Quotation", 'label': __('Quotation'), 'reqd': 1}
            ],
            'primary_action': function(){
                d.hide();
                var values = d.get_values();
                frappe.call({
                    'method': "microsynth.microsynth.quotation.link_quotation_to_order",
                    'args':{
                        'sales_order': values.sales_order,
                        'quotation': values.quotation
                    },
                    'callback': function(r) {
                        console.log(r.message);
                        if (r.message) {
                            frappe.set_route("Form", "Sales Order", r.message);
                        } else {
                            frappe.show_alert("Internal Error")
                        }
                    }
                });
            },
            'primary_action_label': __('Cancel & Amend'),
            'title': __('Link quote to a new Sales Order & pull quote rates')
        });
        d.show();
    }
}


function ensure_contact_has_webshop_account(frm) {
    return new Promise(resolve => {
        // If there is no contact person -> continue normally
        if (!frm.doc.contact_person) {
            resolve(true);
            return;
        }
        frappe.call({
            'method': 'frappe.client.get_value',
            'args': {
                'doctype': 'Contact',
                'filters': { 'name': frm.doc.contact_person },
                'fieldname': 'has_webshop_account'
            },
            callback: function (r) {
                const has = r.message ? r.message.has_webshop_account : null;

                // If the contact HAS a webshop account → continue
                if (has === 1) {
                    resolve(true);
                    return;
                }

                // Otherwise show confirm dialog
                const escaped_contact = frappe.utils.escape_html(frm.doc.contact_person);
                const msg = `
                    <b>No Webshop Account</b> found for Contact Person
                    <code>${escaped_contact}</code>.<br>
                    A Webshop Account is strongly recommended.<br><br>
                    Click <b>Yes</b> to abort submission and fix the Contact Person in the section
                    'Address and Contact'.<br>
                    Click <b>No</b> to continue at your own risk.
                `;
                frappe.confirm(
                    msg,
                    // YES -> Abort submission
                    function () {
                        frappe.msgprint(__("Submission cancelled. Please select a Contact Person with a Webshop Account."));
                        resolve(false);
                    },
                    // NO -> Continue submission
                    function () {
                        resolve(true);
                    }
                );
            }
        });
    });
}


function render_accounts_table(accounts) {
    let html = `<table class="table table-bordered">
        <thead>
            <tr>
                <th>${__("Credit Account")}</th>
                <th>${__("Account Name")}</th>
                <th>${__("Account Type")}</th>
                <th>${__("Product Types")}</th>
                <th>${__("Expiry Date")}</th>
            </tr>
        </thead>
        <tbody>`;

    accounts.forEach(a => {
        html += `
            <tr>
                <td>${a.name}</td>
                <td>${a.account_name || ''}</td>
                <td>${a.account_type || ''}</td>
                <td>${a.product_types || ''}</td>
                <td>${a.expiry_date || ''}</td>
            </tr>
        `;
    });
    html += `</tbody></table>`;
    return html;
}

function add_accounts_to_sales_order(frm, accounts) {
    accounts.forEach(a => {
        let row = frm.add_child("credit_accounts");
        row.credit_account = a.name;
    });
    frm.refresh_field("credit_accounts");
}

function show_credit_account_dialog(frm) {
    frappe.call({
        'method': "microsynth.microsynth.credits.get_available_credit_accounts",
        'args': {
            'company': frm.doc.company,
            'currency': frm.doc.currency,
            'customer': frm.doc.customer,
            'product_types': frm.doc.product_type ? [frm.doc.product_type] : []
        },
        'callback': function (r) {
            if (r.exc) return;

            const accounts = r.message || [];
            console.log(r.message);
            if (accounts.length === 0) {
                frappe.msgprint(__("No Credit Accounts available."));
                return;
            }

            // Build table rows
            const rows_html = accounts.map((a, i) => `
                <tr data-index="${i}">
                    <td><input type="checkbox" class="account-select"></td>
                    <td>${a.name}</td>
                    <td>${a.account_name || ''}</td>
                    <td>${a.account_type || ''}</td>
                    <td>${a.product_types || ''}</td>
                </tr>
            `).join("");

            const dialog = new frappe.ui.Dialog({
                'title': __("Select Credit Account(s) to deduct this Sales Order from:"),
                'primary_action_label': __("Select"),
                primary_action() {
                    const body = dialog.$wrapper.find(".credit-account-table");
                    const selected = [];

                    body.find("tr").each(function () {
                        const chk = $(this).find(".account-select").is(":checked");
                        if (chk) {
                            const index = $(this).data("index");
                            selected.push(accounts[index]);
                        }
                    });
                    if (selected.length === 0) {
                        frappe.msgprint(__("Please select at least one Credit Account."));
                        return;
                    }
                    // Avoid duplicates
                    const already = (frm.doc.credit_accounts || []).map(r => r.credit_account);

                    const to_add = selected.filter(a => !already.includes(a.name));
                    if (to_add.length === 0) {
                        frappe.msgprint(__("All selected Credit Accounts are already added."));
                        return;
                    }
                    add_accounts_to_sales_order(frm, to_add);
                    frm.save();
                    return;
                },
                secondary_action_label: __("Close"),
                secondary_action() {
                    return;
                }
            });
            dialog.$body.append(`
                <table class="table table-bordered credit-account-table">
                    <thead>
                        <tr>
                            <th>${__("Select")}</th>
                            <th>${__("Credit Account")}</th>
                            <th>${__("Account Name")}</th>
                            <th>${__("Account Type")}</th>
                            <th>${__("Product Types")}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows_html}
                    </tbody>
                </table>
            `);
            dialog.show();
        }
    });
}
