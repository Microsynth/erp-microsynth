
// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Payment"),
        'items': ["Payment Proposal"]
    }
]);

/* Custom script extension for Purchase Invoice */
// iframe interaction handler for invoice entry
window.onmessage = function(e) {
    if (e.data == "close_document") {
        if (cur_frm.is_dirty()) {
            cur_frm.save().then(function() {
                window.top.postMessage("iframe_saved " + cur_frm.doc.name, {});
            });
        } else {
            // all saved, signal can close
            window.top.postMessage("iframe_saved " + cur_frm.doc.name, {});
        }
    }
}

frappe.ui.form.on('Purchase Invoice', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }

        if (!frm.doc.__islocal && frm.doc.docstatus == 0 && !frm.doc.in_approval) {
            frm.add_custom_button(__("Request Approval"), function() {
                request_approval(frm);
            });
        }

        if (!frm.doc.__islocal && frm.doc.docstatus == 0 && frm.doc.in_approval && frappe.user.has_role("Accounts Manager")) {
            frm.add_custom_button(__("Reassign"), function() {
                reassign(frm);
            });
        }

        if (frm.doc.docstatus == 1 && frm.doc.is_return && !frm.doc.return_against) {
            frm.add_custom_button(__("Book as Deposit"), function() {
                frappe.msgprint("Will be automatically done right after approval if 'Is Return (Debit Note)', Return Type is 'Deduct from Invoice' and return_against is None.");
                //book_as_deposit(frm);
            });
        }

        if (!frm.doc.__islocal) {
            frm.add_custom_button("Related Documents", function () {
                frappe.set_route("query-report", "Purchase Document Overview", {
                    "document_id": frm.doc.name
                });
            }, __("View"));
        }

        if (frm.doc.in_approval) {
            cur_frm.set_df_property('approver', 'read_only', true);
        } else {
            cur_frm.set_df_property('approver', 'read_only', false);
        }

        if (!frm.doc.supplier_address) {
            frappe.throw("Please set a Supplier Address on this Purchase Invoice.");
            frappe.validated = false;
        }

        if (frm.doc.due_date < frappe.datetime.get_today() && frm.doc.status != "Paid") {
            frm.dashboard.add_comment('Due date <b>exceeded</b>', 'red', true);
        }

        hide_in_words();
    },
    before_save(frm) {
        if (frm.doc.is_return && !frm.doc.return_type) {
            frappe.msgprint("Please set a Return Type.");
        }
    },
    before_submit() {
        frappe.msgprint("Please use the Approval Manager to submit.");
        frappe.validated = false;
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
    },
    is_return(frm) {
        // remove return_type if is_return was removed
        if (!frm.doc.is_return && frm.doc.return_type) {
            cur_frm.set_value('return_type', null);
        }
    },
    supplier(frm) {
        // fetch Default Item, Default Taxes, Payment Terms
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.supplier_change_fetches',
            'args': {
                'supplier_id': frm.doc.supplier,
                'company': frm.doc.company
            },
            'callback': function(response) {
                if (response.message.default_approver) {
                    cur_frm.set_value('approver', response.message.default_approver);
                } else {
                    frappe.msgprint("Supplier " + frm.doc.supplier + " has no default Approver.");
                }
                if (response.message.payment_terms_template) {
                    cur_frm.set_value('payment_terms_template', response.message.payment_terms_template);
                } else {
                    frappe.msgprint("Supplier " + frm.doc.supplier + " has no default Payment Terms Template.");
                }
                if ((frm.doc.items || []).length == 1) {
                    if (response.message.default_item_code && response.message.default_item_name) {
                        frappe.model.set_value(frm.doc.items[0].doctype, frm.doc.items[0].name, "item_code", response.message.default_item_code);
                        frappe.model.set_value(frm.doc.items[0].doctype, frm.doc.items[0].name, "item_name", response.message.default_item_name);
                    } else {
                        frappe.msgprint("Supplier " + frm.doc.supplier + " has no default Item.");
                    }
                    if (response.message.expense_account) {
                        frappe.model.set_value(frm.doc.items[0].doctype, frm.doc.items[0].name, "expense_account", response.message.expense_account);
                    } else {
                        frappe.msgprint("The default Item " + response.message.default_item_code + " of Supplier " + frm.doc.supplier + " has no Default Expense Account.");
                    }
                    if (response.message.cost_center) {
                        frappe.model.set_value(frm.doc.items[0].doctype, frm.doc.items[0].name, "cost_center", response.message.cost_center);
                    }
                } else {
                    frappe.msgprint("None or multiple Items, unable to change Item according to Supplier.");
                }
                if (response.message.taxes_and_charges) {
                    setTimeout(() => {
                        cur_frm.set_value('taxes_and_charges', response.message.taxes_and_charges);
                    }, 400);
                } else {
                    frappe.msgprint("Supplier " + frm.doc.supplier + " has no default Tax Template for Company " + frm.doc.company + ".");
                }
                frappe.show_alert( __("Default Approver, Item, Taxes and Payment Terms Template fetched from new supplier") );
            }
        });
    }
});


function request_approval(frm) {
    frappe.prompt([
        {'fieldname': 'assign_to', 'fieldtype': 'Link', 'label': __('Approver'), 'options':'User', 'default': cur_frm.doc.approver, 'reqd': 1}
    ],
    function(values){
        if (values.assign_to != cur_frm.doc.approver) {
            frappe.confirm(
                __("Are you sure that you want to change the approver from " + cur_frm.doc.approver + " to " + values.assign_to + "?"),
                function () {
                    // yes
                    frappe.call({
                        'method': 'microsynth.microsynth.purchasing.create_approval_request',
                        'args': {
                            'assign_to': values.assign_to,
                            'dt': cur_frm.doc.doctype,
                            'dn': cur_frm.doc.name
                        },
                        "callback": function(response) {
                            if (response.message) {
                                frappe.show_alert( __("Approval request created") );
                                cur_frm.reload_doc();
                            } else {
                                frappe.show_alert( __("No approval request created. This Purchase Invoice seems to be already assigned to an approver.") );
                            }
                        }
                    });
                },
                function () {
                    // no
                    frappe.show_alert('No approval request created.');
                }
            );
        } else {
            frappe.call({
                'method': 'microsynth.microsynth.purchasing.create_approval_request',
                'args': {
                    'assign_to': values.assign_to,
                    'dt': cur_frm.doc.doctype,
                    'dn': cur_frm.doc.name
                },
                "callback": function(response) {
                    if (response.message) {
                        frappe.show_alert( __("Approval request created") );
                        cur_frm.reload_doc();
                    } else {
                        frappe.show_alert( __("This Purchase Invoice seems to be already assigned to an approver.") );
                    }
                }
            });
        }
    },
    __('Please choose an approver'),
    __('Request approval')
    )
}


function reassign(frm) {
    frappe.prompt([
        {'fieldname': 'assign_to', 'fieldtype': 'Link', 'label': __('Approver'), 'options':'User', 'reqd': 1}
    ],
    function(values){
        frappe.confirm(
            __("Are you sure that you want to change the approver from " + cur_frm.doc.approver + " to " + values.assign_to + "?"),
            function () {
                // yes
                frappe.call({
                    'method': 'microsynth.microsynth.purchasing.reassign_purchase_invoice',
                    'args': {
                        'assign_to': values.assign_to,
                        'dt': cur_frm.doc.doctype,
                        'dn': cur_frm.doc.name
                    },
                    "callback": function(response) {
                        if (response.message) {
                            frappe.show_alert( __("Approval request created") );
                            cur_frm.reload_doc();
                        } else {
                            frappe.show_alert( __("Error: No approval request created.") );
                        }
                    }
                });
            },
            function () {
                // no
                frappe.show_alert('No changes made.');
            }
        );
    },
    __('Please choose a new approver'),
    __('Request approval')
    )
}


function book_as_deposit(frm) {
    frappe.call({
        'method': 'microsynth.microsynth.purchasing.book_as_deposit',
        'args': {
            'purchase_invoice_id': cur_frm.doc.name
        },
        "callback": function(response) {
            if (response.message) {
                window.open("/" + frappe.utils.get_form_link("Journal Entry", response.message), "_blank");
            } else {
                frappe.show_alert( __("Error: No Journal Entry created.") );
            }
        }
    });
}
