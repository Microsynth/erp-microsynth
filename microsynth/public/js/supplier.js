/* Custom script extension for Supplier */


frappe.ui.form.on('Supplier', {
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
                                <th>UOM</th>
                                <th>Supplier Part No</th>
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
