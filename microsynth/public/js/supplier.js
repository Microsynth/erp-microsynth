/* Custom script extension for Supplier */


frappe.ui.form.on('Supplier', {
    onload(frm) {
        frm._original_direct_debit_enabled = Number(frm.doc.direct_debit_enabled || 0);
        frm._skip_direct_debit_invoice_prompt = false;
    },
    refresh(frm) {
        cur_frm.fields_dict['default_item'].get_query = function() {
            return {
                filters: {
                    'is_purchase_item': 1,
                    'disabled': 0
                }
            };
        };

        frm.set_query('default_tax_template', 'accounts', function(doc, cdt, cdn) {
            var d = locals[cdt][cdn];
            var filters = {
                'company': d.company
            }
            return {'filters': filters}
        });

        frm.set_query('order_contact', function() {
            return {
                query: "frappe.contacts.doctype.contact.contact.contact_query",
                filters: {
                    link_doctype: "Supplier",
                    link_name: frm.doc.name
                }
            };
        });

        if (frm.doc.supplier_shops.length > 0 && frm.doc.supplier_shops[0].webshop_url) {
            frm.add_custom_button(__('Open Supplier Webshop'), function() {
                window.open(
                    frm.doc.supplier_shops[0].webshop_url,
                    '_blank' // open in a new window.
                );
            }).addClass("btn-primary");
        }

        if (frm._original_direct_debit_enabled === undefined) {
            frm._original_direct_debit_enabled = Number(frm.doc.direct_debit_enabled || 0);
        }
    },
    before_save(frm) {
        if (frm.is_new()) {
            return;
        }

        if (frm._skip_direct_debit_invoice_prompt) {
            return;
        }

        const was_enabled = Number(frm._original_direct_debit_enabled || 0) === 1;
        const is_enabled = Number(frm.doc.direct_debit_enabled || 0) === 1;
        if (was_enabled || !is_enabled) {
            return;
        }

        frappe.validated = false;
        prompt_direct_debit_invoice_decision(frm);
    },
    after_save(frm) {
        frm._original_direct_debit_enabled = Number(frm.doc.direct_debit_enabled || 0);
        frm._skip_direct_debit_invoice_prompt = false;
    },
    disabled: function(frm) {
        if (!frm.doc.disabled) {
            // User re-enabled the supplier → ok
            return;
        }
        frappe.call({
            'method': "microsynth.microsynth.purchasing.get_items_using_supplier",
            'args': { supplier: frm.doc.name },
            'callback': function(r) {
                let items = r.message || [];

                if (items.length === 0) {
                    // No affected items → allow disabling
                    return;
                }
                // Build HTML table listing the affected items
                let html = `
                    <p>Should the Supplier <b>remain enabled?</b><br><br>This <b>Supplier</b> is still <b>linked to enabled Items</b>:</p>
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>Item Code</th>
                                <th>Item Name</th>
                                <th>unit</th>
                                <th>Supplier Item Code</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                items.forEach(it => {
                    html += `
                        <tr>
                            <td>${it.name}</td>
                            <td>${it.item_name}</td>
                            <td>${it.stock_uom}</td>
                            <td>${it.supplier_part_no || ""}</td>
                        </tr>`;
                });
                html += "</tbody></table>";

                // Confirmation dialog
                frappe.confirm(
                    html + "<br><i>(Yes = keep enabled, No = continue to disable anyway)</i>",

                    function() {  // YES = keep enabled
                        frappe.show_alert(__("Supplier kept enabled."));
                        frm.set_value("disabled", 0);
                        frm.refresh_field("disabled");
                    },

                    function() {  // NO = disable anyway
                        frm.set_value("disabled", 1);
                        frm.refresh_field("disabled");
                    }
                );
            }
        });
    }
});


function continue_supplier_save(frm) {
    frm._skip_direct_debit_invoice_prompt = true;
    frm.save().catch(function() {
        frm._skip_direct_debit_invoice_prompt = false;
    });
}


function prompt_direct_debit_invoice_decision(frm) {
    frappe.call({
        method: 'microsynth.microsynth.purchasing.get_open_purchase_invoices',
        args: {
            supplier: frm.doc.name
        },
        callback: function(response) {
            const invoices = response.message || [];

            if (invoices.length === 0) {
                continue_supplier_save(frm);
                return;
            }

            let html = `
                <p>
                    This Supplier still has <b>open Purchase Invoices</b> that can be included in future <b>Payment Proposals</b>.<br><br>
                    Do you want to <b>exclude all listed invoices</b> from future Payment Proposals now?
                </p>
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Purchase Invoice</th>
                            <th>Supplier Invoice No.</th>
                            <th>Due Date</th>
                            <th>Outstanding Amount</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            invoices.forEach(function(invoice) {
                const outstanding = format_currency(invoice.outstanding_amount || 0, invoice.currency);
                html += `
                    <tr>
                        <td>${invoice.name}</td>
                        <td>${invoice.bill_no || ''}</td>
                        <td>${invoice.due_date || ''}</td>
                        <td>${outstanding}</td>
                    </tr>
                `;
            });

            html += '</tbody></table>';

            frappe.confirm(
                html + '<br><i>(Yes = exclude all listed invoices, No = keep all invoices unchanged)</i>',
                function() {
                    frappe.call({
                        method: 'microsynth.microsynth.purchasing.exclude_purchase_invoices_from_future_payment_proposals',
                        args: {
                            purchase_invoices: invoices.map(function(invoice) { return invoice.name; })
                        },
                        callback: function(update_response) {
                            const updated_count = (update_response.message && update_response.message.updated_count) || 0;
                            frappe.show_alert(`${updated_count} Purchase Invoices were excluded from future Payment Proposals.`);
                            continue_supplier_save(frm);
                        },
                        error: function() {
                            frappe.msgprint(__('Unable to update Purchase Invoices. Please try again.'));
                        }
                    });
                },
                function() {
                    frappe.show_alert(__('Purchase Invoices were left unchanged.'));
                    continue_supplier_save(frm);
                }
            );
        },
        error: function() {
            frappe.msgprint(__('Unable to check open Purchase Invoices. Please try again.'));
        }
    });
}


frappe.ui.form.on('Supplier Shop', {
    password(frm, cdt, cdn) {
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.check_supplier_shop_password',
            'args': {
                "password": frappe.model.get_value(cdt, cdn, "password")
            },
            'callback': function(response) {
                if (!response.message.error) {
                    frappe.show_alert( __("Password ok") );
                } else {
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: response.message.error
                    });
                }
            }
        });
    },
    copy_password(frm, cdt, cdn) {
        if (locals[cdt][cdn].password === "*".repeat(locals[cdt][cdn].password.length)) {
            /* from server */
            frappe.call({
                "method": "microsynth.microsynth.purchasing.decrypt_access_password",
                "args": {
                    "cdn": cdn
                },
                "callback": function(response) {
                    navigator.clipboard.writeText(response.message.password).then(function() {
                        frappe.show_alert( __("Copied") );
                    }, function() {
                        frappe.show_alert( __("No access") );
                    });
                    if (response.message.warning) {
                        frappe.msgprint({
                            title: __('Warning'),
                            indicator: 'orange',
                            message: response.message.warning
                        });
                    }
                }
            });
        } else {
            /* use password value */
            navigator.clipboard.writeText(frappe.model.get_value(cdt, cdn, "password")).then(function() {
                frappe.show_alert( __("Copied") );
            }, function() {
                frappe.show_alert( __("No access") );
            });
        }
    }
});
