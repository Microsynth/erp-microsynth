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

        if (!frm.doc.order_confirmation_no &&
            ['Draft', 'On Hold', 'To Receive and Bill', 'To Receive'].includes(frm.doc.status) &&
            frm.doc.items.length > 0
        ) {
            frm.add_custom_button(__('Send Order by Email'), function() {
                open_mail_dialog(frm, supplier.order_contact, contact.email_id);
            });
            show_order_method(frm);
            // Display internal Item notes in a green banner if the Quotation is in Draft status
            var dashboard_comment_color = 'green';
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
        return new Promise((resolve, reject) => {
            frappe.call({
                'method': "microsynth.microsynth.purchasing.check_po_item_prices",
                'args': { 'purchase_order_name': frm.doc.name },
                'callback': function(r) {
                    const data = r.message;
                    if (!data) return resolve();

                    // --- Case 1: Missing or wrong Price List ---
                    if (data.status === "no_price_list" || data.status === "currency_mismatch") {
                        const msg = `<strong>Missing Price List</strong><br><br>Please set a <strong>Price List</strong> with Currency <strong>${
                            data.price_list_currency || frm.doc.currency
                        }</strong> on this Purchase Order to enable Price checking.<br>Click <strong>No</strong> to submit without a Price List <strong>at your own risk</strong>.`;

                        frappe.confirm(
                            msg,
                            () => {
                                frappe.show_alert("Please set Price List with matching currency before submitting.");
                                reject(); // leave PO as Draft
                            },
                            () => {
                                resolve();
                            }
                        );
                        return;
                    }

                    // --- Case 2: Nothing to add/update ---
                    if ((!data.adds || !data.adds.length) && (!data.updates || !data.updates.length)) {
                        return resolve();
                    }

                    // --- Case 3: Items to add/update ---
                    let message = `Do you want to apply <strong>all</strong> changes below to the Price List <strong>${frm.doc.buying_price_list}</strong> now?<br><br>`;

                    if (data.adds && data.adds.length) {
                        message += "<strong>Prices to Add:</strong><ul>";
                        data.adds.forEach(item => {
                            message += `<li>${item.item_code} (${item.item_name}) with minimum qty ${item.min_qty}: ${item.rate} ${frm.doc.currency}</li>`;
                        });
                        message += "</ul>";
                    }

                    if (data.updates && data.updates.length) {
                        message += "<strong>Prices to Update:</strong><ul>";
                        data.updates.forEach(item => {
                            message += `<li>${item.item_code} (${item.item_name}) with minimum qty ${item.min_qty}: ${item.current_rate} ${frm.doc.currency} → ${item.rate} ${frm.doc.currency} (${item.rate_diff_pct} %)</li>`;
                        });
                        message += "</ul>";
                    }

                    frappe.confirm(
                        message,
                        () => {
                            // User accepts: apply changes
                            frappe.call({
                                'method': "microsynth.microsynth.purchasing.apply_item_price_changes",
                                'args': {
                                    'price_list': frm.doc.buying_price_list,
                                    'adds': JSON.stringify(data.adds || []),
                                    'updates': JSON.stringify(data.updates || [])
                                },
                                'callback': function() {
                                    frappe.show_alert("Item Prices updated.");
                                    resolve();
                                }
                            });
                        },
                        () => {
                            // User ignores all: continue without changes
                            resolve();
                        }
                    );
                }
            });
        });
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
        let has_webshop = supplier.supplier_shops && supplier.supplier_shops.length > 0 && supplier.supplier_shops[0].username;
        if (has_webshop) {
            frm.dashboard.add_comment(__('Order through Webshop, see Supplier {0} for credentials.', [supplier.name]), 'green', true);
            if (supplier.supplier_shops[0].webshop_url) {
                frm.add_custom_button(__('Open Supplier Webshop'), function() {
                    window.open(
                        supplier.supplier_shops[0].webshop_url,
                        '_blank' // open in a new window.
                    );
                }).addClass("btn-primary");
            }
            return;
        }
        if (supplier.order_contact) {
            frappe.db.get_doc('Contact', supplier.order_contact).then(contact => {
                if (contact.email_id) {
                    frm.dashboard.add_comment(__('Order by Email to {0}', [contact.email_id]), 'blue', true);
                } else {
                    frm.dashboard.add_comment(__('⚠️ Order Contact {0} of Supplier {1} has no email address.', [contact.name, supplier.name]), 'orange', true);
                }
            });
        } else {
            frm.dashboard.add_comment(__('⚠️ Order Method unclear: Supplier {0} has no Supplier Shop with a username and no Order Contact with an email.', [supplier.name]), 'red', true);
        }
    });
}
