// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Follow Up"),
        'items': ["Contact Note"]
    }
]);


frappe.ui.form.on('Quotation Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    },
    item_code(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code) {
            pull_item_service_specification(row.item_code, row.quotation_group);
        }
    },
    quotation_group(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code) {
            pull_item_service_specification(row.item_code, row.quotation_group);
        }
    }
});


frappe.ui.form.on('Quotation', {
    refresh(frm){
        // remove Menu > Email if document is not valid
        if (frm.doc.docstatus != 1) {
            var target ="span[data-label='" + __("Email") + "']";
            $(target).parent().parent().remove();
        }

        // Display internal Item notes in a green banner if the Quotation is in Draft status
        if (frm.doc.docstatus == 0 && frm.doc.items.length > 0 && !frappe.user.has_role("NGS Lab User")) {
            var dashboard_comment_color = 'green';
            //cur_frm.dashboard.add_comment("<br>", dashboard_comment_color, true)
            for (var i = 0; i < frm.doc.items.length; i++) {
                if (frm.doc.items[i].item_code) {
                    frappe.call({
                        'method': "frappe.client.get",
                        'args': {
                            "doctype": "Item",
                            "name": frm.doc.items[i].item_code
                        },
                        'callback': function(response) {
                            var item = response.message;
                            if (item.internal_note) {
                                cur_frm.dashboard.add_comment("<b>" + item.item_code + "</b>: " + item.internal_note, dashboard_comment_color, true);
                            }
                        }
                    });
                }
            }
        }

        if (frm.doc.docstatus == 1 && frm.doc.status == "Open" && frm.doc.valid_till >= frappe.datetime.get_today()) {
            frm.add_custom_button(__('Follow Up'), function() {
                follow_up(frm);
            }).addClass("btn-primary");
        }

        if (!frm.doc.__islocal && frm.doc.status == "Ordered") {
            frm.add_custom_button("Related Documents", function () {
                frappe.set_route("query-report", "Sales Document Overview", {
                    "document_id": frm.doc.name
                });
            }, __("View"));
        }

        if (
            frm.doc.docstatus === 1 &&
            frm.doc.valid_till >= frappe.datetime.get_today() &&
            frm.doc.status !== "Lost" &&
            frm.doc.items.length === 1 &&
            frm.doc.items[0].item_code === "6100"
        ) {
            frm.add_custom_button(
                __("Deposit Invoice"),
                () => {
                    create_order_and_deposit_invoice(frm);
                },
                __("Create")
            );
        }

        // replace button "Create > Sales Order" with a custom button
        // that checks if there are already Sales Orders linked to this Quotation
        if (frm.doc.docstatus == 1) {
            setTimeout(function() {
                // remove Create > Sales Order
                $("a[data-label='" + encodeURI(__("Sales Order")) + "']").parent().remove();

                // Add own button to create Sales Order from Quotation
                frm.add_custom_button(__('Sales Order'), function() {
                    frappe.call({
                        'method': "microsynth.microsynth.quotation.get_sales_orders_linked_to_quotation",
                        'args': {
                            'quotation_name': frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message && r.message.length > 0) {
                                let existing_orders = r.message;
                                let message_html = "<p>" + __("The following Sales Orders are already linked to this Quotation:") + "</p><ul>";
                                message_html += `
                                    <table style="border-collapse: collapse;">
                                    <thead>
                                        <tr>
                                        <th style="border:1px solid #ccc; padding:6px;">Sales Order</th>
                                        <th style="border:1px solid #ccc; padding:6px;">Status</th>
                                        <th style="border:1px solid #ccc; padding:6px;">Web Order ID</th>
                                        <th style="border:1px solid #ccc; padding:6px;">PO</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                    `;
                                existing_orders.forEach(so => {
                                    message_html += `
                                        <tr>
                                        <td style="border:1px solid #ccc; padding:6px;">
                                            <a href="/desk#Form/Sales Order/${so.name}" target="_blank">${so.name}</a>
                                        </td>
                                        <td style="border:1px solid #ccc; padding:6px;">${so.status || ''}</td>
                                        <td style="border:1px solid #ccc; padding:6px;">${so.web_order_id || ''}</td>
                                        <td style="border:1px solid #ccc; padding:6px;">${so.po_no || ''}</td>
                                        </tr>
                                    `;
                                });
                                message_html += `</tbody></table>`;
                                message_html += "</ul><p>" + __("Are you sure you want to create a new Sales Order?") + "</p>";
                                frappe.confirm(
                                    message_html,
                                    function() {
                                        // User confirmed to create another Sales Order
                                        frappe.model.open_mapped_doc({
                                            'method': "erpnext.selling.doctype.quotation.quotation.make_sales_order",
                                            'frm': cur_frm
                                        });
                                    },
                                    function() {
                                        // User canceled
                                    }
                                );
                            } else {
                                // No Sales Orders found — create a new one
                                frappe.model.open_mapped_doc({
                                    'method': "erpnext.selling.doctype.quotation.quotation.make_sales_order",
                                    'frm': cur_frm
                                });
                            }
                        }
                    });
                }, __("Create"));
            }, 1000);
        }

        if (frm.doc.docstatus > 0) {
            frappe.call({
                'method': 'microsynth.microsynth.doctype.contact_note.contact_note.get_follow_ups',
                'args': {
                    'quotation': frm.doc.name
                },
                'callback': function(response) {
                    let contact_notes = response.message;
                    let url_string = "";
                    for (var i = 0; i < contact_notes.length; i++) {
                        if (i > 0) {
                            url_string += ", ";
                        }
                        url_string += "<a href='" + contact_notes[i].url + "'>" + contact_notes[i].name + " (" + contact_notes[i].date + ")</a>"
                    }
                    if (contact_notes.length > 0) {
                        cur_frm.dashboard.add_comment("This Quotation was followed up with Contact Note " + url_string, "green", true);
                    }
                }
            });
        }

        // run code with a delay because the core framework code is slower than the refresh trigger and would overwrite it
        setTimeout(function(){
            cur_frm.fields_dict['customer_address'].get_query = function(doc) {          //gets field you want to filter
                return {
                    filters: {
                        "link_doctype": "Customer",
                        "link_name": cur_frm.doc.party_name,
                        "address_type": "Billing"
                    }
                }
            }
        }, 500);

        setTimeout(function(){
            if (frm.doc.__islocal) {
                frm.set_value('lost_reasons', null);  // remove lost reasons, e.g. when duplicating a Quotation
                assert_customer_fields(frm);
            }
        }, 500);

        hide_in_words();

        // fetch Sales Manager from Customer if not yet set
        if (frm.doc.__islocal && (!frm.doc.sales_manager || frm.doc.sales_manager == "")) {
            frappe.call({
                'method': 'frappe.client.get_value',
                'args': {
                    'doctype': 'Customer',
                    'fieldname': 'account_manager',
                    'filters': {
                        'name': cur_frm.doc.party_name,
                    }
                },
                callback: function(r){
                    frm.doc.sales_manager = r.message.account_manager;
                }
            });
        }

        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            });
        }

        if ((frm.doc.__islocal || frm.doc.status == "Draft") && frm.doc.valid_till && frm.doc.valid_till < frappe.datetime.get_today()) {
            frappe.msgprint({
                title: __('Warning'),
                indicator: 'orange',
                message: __("Please enter a Valid Till date that is in the future.")
            });
        }
    },

    before_save(frm) {
        // assert customer master fields on initial save
        if (frm.doc.__islocal) {
            assert_customer_fields(frm);
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
                            Click <b>Yes</b> to abort submission and fix the Contact Person.<br>
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
    },

    on_submit(frm) {
        // this is a hack to prevent not allowed to change discount amount after submit because the form has an unrounded value on an item
        cur_frm.reload_doc();
    },

    validate(frm) {
        if (!frm.doc.product_type) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'red',
                message: __("Please set the Product Type.")
            });
            frappe.validated=false;
        }
        // block Product Type NGS
        if (frm.doc.product_type === "NGS") {
            frappe.throw(__("Product Type NGS is deprecated. Please use Genetic Analysis instead."))
        }
    },

    product_type(frm){
        if (frm.doc.product_type == 'Oligos') {
            frm.set_value('quotation_type', 'Synthesis');
        } else if (frm.doc.product_type == 'Labels') {
            frm.set_value('quotation_type', 'Labels');
        } else if (frm.doc.product_type == 'Sequencing') {
            frm.set_value('quotation_type', 'Sanger Sequencing');
        } else if (['Genetic Analysis', 'NGS', 'FLA', 'Project', 'Material', 'Service'].includes(frm.doc.product_type)) {
            frm.set_value('quotation_type', 'Genetic Analysis');
        } else {
            frm.set_value('quotation_type', '');
        }
    },

    customer_name(frm) {
        // set title to customer name
        if (frm.doc.customer_name && frm.doc.customer_name != frm.doc.title) {
            frm.set_value("title", frm.doc.customer_name);
        }
    },

    company(frm) {
        if (!frm.doc.company) return;
        // Fetch company abbreviation
        frappe.call({
            "method": "frappe.client.get_value",
            "args": {
                "doctype": "Company",
                "filters": { "name": frm.doc.company },
                "fieldname": "abbr"
            },
            "callback": function(r) {
                if (r.message && r.message.abbr) {
                    let warehouse = "Stores - " + r.message.abbr;  // assuming that this is always the correct Warehouse
                    // Update each item
                    (frm.doc.items || []).forEach(item => {
                        if (item.warehouse !== warehouse) {
                            item.warehouse = warehouse;
                        }
                    });
                    frm.refresh_field("items");
                }
            }
        });
    }
});

/* this function will pull
 * territory, currency and selling_price_list
 * from the customer master data */
function assert_customer_fields(frm) {
    if ((frm.doc.quotation_to === "Customer") && (frm.doc.party_name)) {
        frappe.call({
            'method': "frappe.client.get",
            'args': {
                'doctype': "Customer",
                'name': frm.doc.party_name
            },
            'asyc': false,
            'callback': function(r) {
                var customer = r.message;
                if (customer.territory) { cur_frm.set_value("territory", customer.territory); }
                if (customer.default_currency) { cur_frm.set_value("currency", customer.default_currency); }
                if (customer.default_price_list && !frm.doc.selling_price_list.includes("Contract Research")) {  // do not overwrite an already set Contract Research price list
                    cur_frm.set_value("selling_price_list", customer.default_price_list);
                }
            }
        });
    }
}

/* load the item and fetch its service specification if available */
function pull_item_service_specification(item_code, quotation_group) {
    if (item_code) {
        frappe.call({
            'method': "frappe.client.get",
            'args': {
                'doctype': "Item",
                'name': item_code
            },
            'callback': function(r) {
                var item = r.message;
                if (item.service_specification) {
                    if (quotation_group) {
                        // find group
                        for (var i = 0; i < cur_frm.doc.quotations_groups.length; i++) {
                            if (quotation_group == cur_frm.doc.quotations_groups[i].group_name) {
                                if (!cur_frm.doc.quotations_groups[i].service_description || !cur_frm.doc.quotations_groups[i].service_description.includes(item.service_description)) {
                                    // add service description to Quotation Groups
                                    frappe.model.set_value(cur_frm.doc.quotations_groups[i].doctype,
                                                            cur_frm.doc.quotations_groups[i].name,
                                                            "service_description",
                                                            cur_frm.doc.quotations_groups[i].service_description ? cur_frm.doc.quotations_groups[i].service_description + item.service_specification : item.service_specification);
                                    // remove service description from general service description
                                    if (cur_frm.doc.service_specification && cur_frm.doc.service_specification.includes(item.service_specification)) {
                                        cur_frm.set_value("service_specification", cur_frm.doc.service_specification.replace(item.service_specification, ""));
                                    }
                                }
                            }
                        }
                    } else {
                        if (cur_frm.doc.service_specification) {
                            if (!cur_frm.doc.service_specification.includes(item.service_specification)) {
                                cur_frm.set_value("service_specification", cur_frm.doc.service_specification /* + "<p>&nbsp;</p>" */ + item.service_specification);
                            }
                        } else {
                            cur_frm.set_value("service_specification", "<h3>Service Description</h3>" + item.service_specification);
                        }
                    }
                }
            }
        });
    }
}


function follow_up(frm){
    frappe.model.open_mapped_doc({
        'method': 'microsynth.microsynth.doctype.contact_note.contact_note.create_new_follow_up',
        'args': {
            'quotation': frm.doc.name
        },
        'frm': frm
    })
}


function create_order_and_deposit_invoice(frm) {
    frappe.call({
        'method': "microsynth.microsynth.credits.get_available_credit_accounts",
        'args': {
            'company': frm.doc.company,
            'currency': frm.doc.currency,
            'customer': frm.doc.party_name,
            'product_types': frm.doc.product_type ? [frm.doc.product_type] : [],
            'account_type': 'Standard'
        },
        'callback': function (r) {
            if (r.exc) return;

            const accounts = r.message || [];
            if (accounts.length === 0) {
                const contact_link = `<a href="/desk#Form/Contact/${encodeURIComponent(frm.doc.contact_person)}" target="_blank">
                    ${frm.doc.contact_person}
                </a>`;

                frappe.msgprint({
                    title: __("No Standard Credit Accounts"),
                    indicator: "red",
                    message: __(
                        `No Standard Credit Accounts available for Customer ${frm.doc.party_name} in Currency ${frm.doc.currency}
                        with Product Type ${frm.doc.product_type} for Company ${frm.doc.company}.<br>
                        Please open Contact ${contact_link} and use the button <b>Create > Credit Account</b> to create one
                        (only available if the Contact has a Webshop Account).<br>Then try again here.`
                    )
                });
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
                'title': __("Select one Credit Account to create a deposit invoice for:"),
                'primary_action_label': __("Select"),
                'primary_action'() {
                    const body = dialog.$wrapper.find(".credit-account-table");
                    const selected = [];

                    body.find("tr").each(function () {
                        const chk = $(this).find(".account-select").is(":checked");
                        if (chk) {
                            const index = $(this).data("index");
                            selected.push(accounts[index]);
                        }
                    });
                    if (selected.length !== 1) {
                        frappe.msgprint(__("Please select exactly one Credit Account."));
                        return;
                    }
                    // create and submit a Sales Order to set the QTN to Ordered using the standard function from core
                    // create, submit and open a Deposit Invoice linked to the selected Credit Account via Sales Invoice.credit_account and using the Item Name from this Quotation
                    frappe.call({
                        'method': "microsynth.microsynth.credits.create_so_and_deposit_invoice",
                        'freeze': true,
                        'freeze_message': __("Creating Sales Order and Deposit Invoice..."),
                        'args': {
                            'quotation_id': frm.doc.name,
                            'credit_account': selected[0].name
                        },
                        'callback': function (r) {
                            if (r.exc) return;

                            if (!r.message || !r.message.sales_invoice) {
                                frappe.msgprint(__("An unexpected error occurred."));
                                return;
                            }
                            frappe.set_route("Form", "Sales Invoice", r.message.sales_invoice);
                        }
                    });
                },
                'secondary_action_label': __("Close"),
                'secondary_action'() {
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
