try {
    cur_frm.dashboard.add_transactions([
        {
            'label': 'Pre Sales',
            'items': ['Standing Quotation']
        },
        {
            'label': 'Quality Management',
            'items': ['QM Document']
        }
    ]);
} catch { /* do nothing for older versions */ }


function has_credits(frm) {
    var return_value;
    frappe.call({
        'method': 'microsynth.microsynth.credits.has_credits',
        'args': {
            'customer': frm.doc.name
        },
        "async": false,
        'callback': function(response) {
            return_value = response.message;
        }
    });
    return return_value;
}


frappe.ui.form.on('Customer', {
    refresh(frm) {
        // show button "Contacts" if Customer has not Status "Disabled", directing to the Customer Finder
        if (frm.doc.disabled != 1) {
            frm.add_custom_button(__("Contacts"), function() {
                frappe.set_route("query-report", "Customer Finder", {'customer_id': frm.doc.name});
            });
        }
        // show button "Customer Credits" only if Customer has credits for any company
        if (has_credits(frm)) {
            frm.add_custom_button(__("Customer Credits"), function() {
                frappe.set_route("query-report", "Customer Credits", {'customer': frm.doc.name, 'company': frm.doc.default_company});
            });
        };
        if ((!frm.doc.__islocal) && (frm.doc.default_price_list)) {
            frm.add_custom_button(__("Gecko Export"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.migration.export_customer_to_gecko",
                    "args": {
                        "customer_name":frm.doc.name
                    }
                })
            });
            frm.add_custom_button(__("Price List"), function() {
                frappe.set_route("query-report", "Pricing Configurator", {'price_list': frm.doc.default_price_list});
            });
            if (!frm.doc.disabled) {
                frappe.db.get_value('Price List', frm.doc.default_price_list, ["enabled"], function(value) {
                    if (!value["enabled"]) {
                        // Show a warning if Default Price List is disabled
                        frappe.msgprint({
                            title: __('Warning'),
                            indicator: 'orange',
                            message: __("The Default Price List <b>" + frm.doc.default_price_list + "</b> of this Customer is <b>disabled</b>.<br><br>Please consider to enable it.")
                        });
                    }
                });
            }
        };
        if ((!frm.doc.__islocal) && (frm.doc.invoicing_method === "Email") && (!frm.doc.invoice_to) && (!frm.doc.disabled)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'orange',
                message: __("Please select an <strong>invoice to</strong> contact with an email address.")
            });
        }
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Payment Reminder"), function() {
                create_payment_reminder(frm);
            }, __("Create") );
        }
        if (!frm.doc.__islocal && !frm.doc.disabled && frm.doc.invoice_to) {
            frm.add_custom_button(__("Price List PDF"), function () {
                const encodedContact = encodeURIComponent(frm.doc.invoice_to);
                const url = frappe.urllib.get_full_url(
                    "/api/method/microsynth.microsynth.webshop.prepare_price_list_pdf_download?contact=" + encodedContact
                );
                const w = window.open(url);
                if (!w) {
                    frappe.msgprint(__("Please enable pop-ups"));
                }
            }, __("Create"));
        }
        if ((!frm.doc.__islocal)
            && ['ARIBA', 'Paynet', 'GEP', 'Scientist'].includes(frm.doc.invoicing_method)
            && (!frm.doc.invoice_network_id)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'orange',
                message: __("Please set the Invoice Network ID or select an Invoicing Method that does not require an Invoice Network ID.")
            });
        }
    },
    validate(frm) {
        if ((!frm.doc.__islocal) && (frm.doc.invoicing_method === "Email") && (!frm.doc.invoice_to) && (!frm.doc.disabled)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'red',
                message: __("Please select an <strong>invoice to</strong> contact with an email address.<br>Changes are <strong>not saved</strong>.")
            });
            frappe.validated=false;
        }
        if (!frm.doc.__islocal && frm.doc.disabled && !frm.doc.__checked_contacts) {
            (async function () {
                const customer_id = frm.doc.name;

                const getOpenDocsHtml = (docs) =>
                    docs.map(doc => `<li>${doc.doctype}: <a href="${doc.url}" target="_blank">${doc.name}</a></li>`).join("");

                const showDisableDialog = (to_disable, not_to_disable) => {
                    const toDisableHtml = getOpenDocsHtml(to_disable);
                    const notToDisableHtml = not_to_disable.length > 0
                        ? "<br>" +
                        __("The following linked records will <b>not</b> be disabled since they are used on a non-completed document or another Customer:") +
                        "<br><br><ul>" + getOpenDocsHtml(not_to_disable) + "</ul>"
                        : "";

                    frappe.confirm(
                        __("Would you like to also <b>disable</b> the following Contacts and Addresses linking to this Customer?<br><ul>{0}</ul>", [toDisableHtml]) +
                        notToDisableHtml,
                        async function () {
                            await frappe.call({
                                method: "microsynth.microsynth.utils.disable_linked_contacts_addresses",
                                args: { links: to_disable }
                            });
                            frappe.msgprint(__("Linked records disabled."));
                            frm.doc.__checked_contacts = true;
                            frm.save();
                        },
                        function () {
                            frm.doc.__checked_contacts = true;
                            frm.save();
                        }
                    );
                };

                const checkContactsAndAddresses = async () => {
                    const result = await frappe.call({
                        method: "microsynth.microsynth.utils.check_linked_contacts_addresses",
                        args: { customer_id }
                    });
                    const { to_disable = [], not_to_disable = [] } = result.message || {};

                    if (to_disable.length > 0) {
                        showDisableDialog(to_disable, not_to_disable);
                    } else {
                        frm.doc.__checked_contacts = true;
                        frm.save();
                    }
                };

                // First check for open documents
                const resultOpenDocs = await frappe.call({
                    method: "microsynth.microsynth.utils.get_open_documents_for_customer",
                    args: { customer_id }
                });

                const open_docs_by_type = resultOpenDocs.message || {};
                const open_docs = Object.entries(open_docs_by_type)
                    .flatMap(([doctype, docs]) => docs.map(doc => ({ ...doc, doctype })));

                if (open_docs.length > 0) {
                    const openDocsHtml = getOpenDocsHtml(open_docs);

                    const dialog = new frappe.ui.Dialog({
                        title: __("Open Documents Found"),
                        indicator: "orange",
                        fields: [
                            {
                                fieldtype: "HTML",
                                fieldname: "message",
                                options: `
                                    <div>
                                        ${__("This Customer is still linked to open documents. You should resolve these before disabling the Customer:")}
                                        <ul>${openDocsHtml}</ul>
                                    </div>`
                            }
                        ],
                        primary_action_label: __("Disable Anyway"),
                        secondary_action_label: __("Close"),
                    });
                    dialog.secondary_action_label = __("Close");

                    dialog.set_primary_action(__("Disable Anyway"), async function () {
                        dialog.hide();
                        await checkContactsAndAddresses();  // ✅ Reuse
                    });

                    dialog.set_secondary_action(function () {
                        dialog.hide();
                    });

                    dialog.show();
                    frappe.validated = false;
                    return;
                }

                // No open docs → just continue
                await checkContactsAndAddresses();

            })();
            frappe.validated = false;
        }

    },
    after_save(frm) {
        if (!frm.doc.disabled) {
            frappe.call({
                "method":"microsynth.microsynth.utils.configure_customer",
                "args": {
                    "customer": frm.doc.name
                },
                "callback": function(response) {
                    cur_frm.reload_doc();
                }
            });
        }
        if (frm.doc.disabled) {
            check_price_list_usage(frm.doc.name, frm.doc.default_price_list);
        }
    },
    tax_id: function(frm) {
        if (frm.doc.tax_id && frm.doc.customer_type != 'Individual') {
            verify_tax_id(frm.doc.tax_id);
        }
    }
});

function fetch_primary_contact(frm) {
    frappe.call({
        'method': 'erpnextswiss.scripts.crm_tools.get_primary_customer_contact',
        'args': {
            'customer': frm.doc.name
        },
        'callback': function(r) {
            if (r.message) {
                var contact = r.message;
                cur_frm.set_value("invoice_to", contact.name);
            }
        }
    });
}


function create_payment_reminder(frm) {
    // ask for which company relation
    frappe.prompt([
            {
                'fieldname': 'company',
                'fieldtype': 'Link',
                'label': __('Company'),
                'options': 'Company',
                'default': frappe.defaults.get_user_default("Company"),
                'reqd': 1}
        ],
        function(values) {
            frappe.call({
                'method': 'erpnextswiss.erpnextswiss.doctype.payment_reminder.payment_reminder.create_reminder_for_customer',
                'args': {
                    'customer': frm.doc.name,
                    'company': values.company,
                    'auto_submit': 0,
                    'max_level': 4
                },
                'callback': function(response) {
                    if (response.message) {
                        frappe.show_alert( __("Reminder created") +
                            ": <a href='/desk#Form/Payment Reminder/" +
                            response.message + "'>" + response.message +
                            "</a>"
                        );
                    } else {
                        frappe.show_alert( __("No overdue invoices (or error)") )
                    }
                }
            });
        },
        __('Select Company'),
        __('OK')
    );
}


function verify_tax_id(tax_id) {
    if (!cur_frm.doc.tax_id.startsWith('CH') &&
        !cur_frm.doc.tax_id.startsWith('GB') &&
        !cur_frm.doc.tax_id.startsWith('IS') &&
        !cur_frm.doc.tax_id.startsWith('TR')) {
        frappe.call({
            method: 'erpnextaustria.erpnextaustria.utils.check_uid',
            args: {
                uid: tax_id
            },
            async: false,
            callback: function(r) {
                if (r.message != true) {
                    frappe.msgprint( __("Invalid Tax ID") );
                    frappe.validated = false;
                } else {
                    frappe.show_alert( __("Tax ID valid") );
                }
            }
        });
    }
}


function check_price_list_usage(customer, price_list) {
    frappe.call({
        "method":"microsynth.microsynth.pricing.is_price_list_used",
        "args": {
            "customer": customer,
            "price_list": price_list,
        },
        "callback": function(response) {
            if (!response.message) {

                var d = new frappe.ui.Dialog({
                    'fields': [
                        {'fieldname': 'text', 'fieldtype': 'HTML'}
                    ],
                    'primary_action': function() {
                        d.hide();
                        // Disable Price List
                        frappe.call({
                            'method': 'microsynth.microsynth.pricing.disable_price_list',
                            'args': {
                                'price_list': price_list
                            },
                            "async": false,
                            'callback': function(response) {
                                frappe.show_alert("Disabled Price List <b>" + price_list + "</b>");
                            }
                        });
                    },
                    'primary_action_label': __("Disable Price List"),
                    'title': __("Found unused Price List")
                });
                d.fields_dict.text.$wrapper.html(__("The Price List <b>" + price_list + "</b> is no longer used by any Customer.<br><br>Do you want to <b>disable</b> it?")),
                d.show();
            }
        }
    });
}
