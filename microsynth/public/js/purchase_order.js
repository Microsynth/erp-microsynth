/* Custom script extension for Purchase Order */
frappe.ui.form.on('Purchase Order', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }

        setTimeout(function () {
            cur_frm.fields_dict.items.grid.get_field('item_code').get_query =
                function(frm, dt, dn) {
                    return {
                        query: "microsynth.microsynth.filters.find_purchasing_items",
                        filters: {
                            "supplier": cur_frm.doc.supplier,
                            "item_group": 'Purchasing',
                            "disabled": 0
                        }
                    };
                };
        }, 1000);

        hide_in_words();

        show_order_method(frm);
    },
    onload(frm) {
        if (!locals.inbound_freight_item) {
            frappe.call({
                'method': 'microsynth.microsynth.purchasing.get_inbound_freight_item',
                'callback': function(r) {
                    if (r.message) {
                        locals.inbound_freight_item = r.message;
                    }
                }
            });
        }
    },
    before_save: function(frm) {
        add_freight_item(frm);
    },
    before_submit: function(frm) {
        // frappe.validated = false;
        // check_prices(frm).then(() => {
        //     frappe.validated = true;
        // }).catch(() => {
        //     frappe.validated = false;
        // });
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);  // common function
        }
        get_supplier_tax_template(frm);
    },
    supplier(frm) {
        get_supplier_tax_template(frm);

        show_order_method(frm);
    }
});


function check_prices(frm) {
    return new Promise((resolve, reject) => {
        // Try to avoid recursion
        if (frm.__price_check_done) return resolve();
        frm.__price_check_done = true;

        frappe.call({
            method: "microsynth.microsynth.purchasing.check_po_item_prices",
            args: { 'purchase_order_name': frm.doc.name },
            callback: function(r) {
                if (!r.message) return resolve();

                const data = r.message;

                // --- Case 1: Missing or wrong Price List ---
                if (data.status === "no_price_list" || data.status === "currency_mismatch") {
                    const msg = `Please set a Price List with Currency ${
                        data.price_list_currency || frm.doc.currency
                    } on this Purchase Order to enable Price checking.`;

                    frappe.confirm(
                        msg,
                        () => {
                            frappe.show_alert("Please set Price List with matching currency before submitting.");
                            reject(); // leave PO as Draft
                        },
                        () => {
                            //frappe.validated = true;
                            resolve();
                        }
                    );
                    return;
                }

                // --- Case 2: Nothing to add/update ---
                if ((!data.adds || !data.adds.length) && (!data.updates || !data.updates.length)) {
                    return resolve();
                }

                // --- Case 3: Show dialog with add/update tables ---
                const dialog = new frappe.ui.Dialog({
                    title: "Item Price Check",
                    fields: [
                        {
                            fieldname: "add_section",
                            fieldtype: "Section Break"
                        },
                        {
                            fieldname: "adds",
                            fieldtype: "Table",
                            label: "Item Prices to Add",
                            cannot_add_rows: true,
                            in_place_edit: true,
                            data: data.adds,
                            get_data: () => dialog.get_value("adds"),
                            fields: [
                                { fieldtype: "Check", fieldname: "apply", label: "Add", default: 1, in_list_view: 1, columns: 1 },
                                { fieldtype: "Data", fieldname: "item_code", label: "Item Code", read_only: 1, in_list_view: 1, columns: 1 },
                                { fieldtype: "Data", fieldname: "item_name", label: "Item Name", read_only: 1, in_list_view: 1, columns: 3 },
                                { fieldtype: "Float", fieldname: "min_qty", label: "Min. Qty", in_list_view: 1, columns: 1 },
                                { fieldtype: "Currency", fieldname: "rate", label: "Rate", in_list_view: 1, columns: 1 }
                            ]
                        },
                        {
                            fieldname: "update_section",
                            fieldtype: "Section Break"
                        },
                        {
                            fieldname: "updates",
                            fieldtype: "Table",
                            label: "Item Prices to Update",
                            cannot_add_rows: true,
                            in_place_edit: true,
                            data: data.updates,
                            get_data: () => dialog.get_value("updates"),
                            fields: [
                                { fieldtype: "Check", fieldname: "apply", label: "Update", default: 1, in_list_view: 1, columns: 1 },
                                { fieldtype: "Data", fieldname: "item_code", label: "Item Code", read_only: 1, in_list_view: 1, columns: 1 },
                                { fieldtype: "Data", fieldname: "item_name", label: "Item Name", read_only: 1, in_list_view: 1, columns: 3 },
                                { fieldtype: "Float", fieldname: "min_qty", label: "Min. Qty", read_only: 1, in_list_view: 1, columns: 1 },
                                { fieldtype: "Currency", fieldname: "current_rate", label: "Current Rate", read_only: 1, in_list_view: 1, columns: 1 },
                                { fieldtype: "Currency", fieldname: "rate", label: "New Rate", in_list_view: 1, columns: 1 },
                                { fieldtype: "Percent", fieldname: "rate_diff_pct", label: "% Change", read_only: 1, in_list_view: 1, columns: 1 }
                            ]
                        }
                    ],
                    primary_action_label: "Add / Update Selected",
                    primary_action(values) {
                        frappe.call({
                            method: "microsynth.microsynth.purchasing.apply_item_price_changes",
                            args: {
                                price_list: frm.doc.buying_price_list,
                                adds: JSON.stringify(values.adds || []),
                                updates: JSON.stringify(values.updates || [])
                            },
                            callback: function() {
                                frappe.show_alert("Item Prices updated.");
                                dialog.hide();
                                // frappe.validated = true;
                                resolve();
                            }
                        });
                    },
                    secondary_action_label: "Ignore All",
                    secondary_action() {
                        dialog.hide();
                        // frappe.validated = true;
                        return resolve();
                        // TODO: Why do I still get "InternalError: too much recursion" and how to resolve it?
                    }
                });

                dialog.show();

                // Make dialog wider
                setTimeout(() => {
                    const modals = document.getElementsByClassName('modal-dialog');
                    if (modals.length > 0) {
                        modals[modals.length - 1].style.width = '1200px';
                    }
                }, 300);
            }
        });
    });
}


function add_freight_item(frm) {
    var freight_item_code = locals.inbound_freight_item;

    if (!freight_item_code) return;

    var already_exists = frm.doc.items.some(function(item) {
        return item.item_code === freight_item_code;
    });

    if (!already_exists) {
        frm.add_child('items', {
            'item_code': freight_item_code,
            'qty': 1,
            'rate': 0,
            'base_rate': 0,
            'amount': 0,
            'base_amount': 0,
            'conversion_factor': 1,
            'schedule_date': frm.doc.schedule_date || frappe.datetime.get_today(),
            'uom': 'Pcs',
            'item_name': 'Inbound Freight',
            'description': 'Inbound Freight Cost'
        });
        frm.refresh_field('items');
    }
}


function get_supplier_tax_template(frm) {
    if ((frm.doc.company) && (frm.doc.supplier)) {
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.get_purchase_tax_template',
            'args': {
                'supplier': frm.doc.supplier,
                'company': frm.doc.company
            },
            'callback': function(response) {
                if (response.message) {
                    console.log("set taxes to: " + response.message);
                    setTimeout(function() {
                        cur_frm.set_value("taxes_and_charges", response.message);
                    }, 500);
                }
            }
        });
    }
}


function open_mail_dialog(frm, contact, email) {
    if (frm.doc.docstatus !== 1) {
        frappe.show_alert(__('Cannot email Purchase Order because it is not submitted.'));
        return;
    }
    if (!contact) {
        frappe.show_alert(__('Please set an Order Contact on Supplier ' + frm.doc.supplier + ' with a valid email address.'));
        return;
    }
    // Fetch the Email Template from server
    const email_template_name = "Purchase Order";
    frappe.call({
        'method': "frappe.client.get",
        'args': {
            'doctype': "Email Template",
            'name': email_template_name
        },
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint('Email Template "'+ email_template_name +'" not found.');
                return;
            }
            new frappe.erpnextswiss.MailComposer({
                'doc': frm.doc,
                'frm': frm,
                'subject': "Purchase Order " + frm.doc.name + " from Microsynth",
                'recipients': email,
                'cc': "purchase@microsynth.ch",
                'attach_document_print': true,
                'txt': r.message.response,
                'check_all_attachments': false,
                'replace_template': true
            });
        }
    });
}


function show_order_method(frm) {
    if (!frm.doc.supplier) return;
    cur_frm.dashboard.clear_comment();

    frappe.db.get_doc('Supplier', frm.doc.supplier).then(supplier => {
        let has_webshop = supplier.supplier_shops && supplier.supplier_shops.length > 0;
        if (has_webshop) {
            frm.dashboard.add_comment(__('Order through Webshop, see Supplier {0} for credentials.', [supplier.name]), 'green', true);
            return;
        }
        if (supplier.order_contact) {
            frappe.db.get_doc('Contact', supplier.order_contact).then(contact => {
                if (contact.email_id) {
                    frm.dashboard.add_comment(__('Order by Email to {0}', [contact.email_id]), 'blue', true);

                    frm.add_custom_button(__('Send Order by Email'), function() {
                        open_mail_dialog(frm, supplier.order_contact, contact.email_id);
                    });
                } else {
                    frm.dashboard.add_comment(__('⚠️ Order Contact {0} of Supplier {1} has no email address.', [contact.name, supplier.name]), 'orange', true);
                }
            });
        } else {
            frm.dashboard.add_comment(__('⚠️ Order Method unclear: Supplier {0} has no Supplier Shop and no Order Contact with an email.', [supplier.name]), 'red', true);
        }
    });
}
