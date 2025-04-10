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

        if (frm.doc.supplier_shops.length > 0 && frm.doc.supplier_shops[0].webshop_url) {
            frm.add_custom_button(__('Open Supplier Webshop'), function() {
                window.open(
                    frm.doc.supplier_shops[0].webshop_url,
                    '_blank' // open in a new window.
                );
            }).addClass("btn-primary");
        }
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
