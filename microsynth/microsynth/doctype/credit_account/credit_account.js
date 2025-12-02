// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Credit Account', {
    refresh: function(frm) {
        // Add Overview button to get to Customer Credits report
        frm.add_custom_button(__('Overview'), function() {
            frappe.set_route('query-report', 'Customer Credits', {
                customer: frm.doc.customer,
                company: frm.doc.company,
                credit_account: frm.doc.name
            });
        });

        if (!frm.doc.__islocal && frm.doc.has_transactions) {
            // Make fields read-only if there are transactions
            cur_frm.set_df_property('customer', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('currency', 'read_only', true);
            cur_frm.set_df_property('account_type', 'read_only', true);

            // frm.add_custom_button(__('Sales Orders'), function() {
            //     frappe.set_route("List", "Sales Order", {"credit_account": frm.doc.name});
            // }, __("View"));

            // frm.add_custom_button(__('Sales Invoices'), function() {
            //     frappe.set_route("List", "Sales Invoice", {"credit_account": frm.doc.name});
            // }, __("View"));
        }
        if (!frm.doc.__islocal && frm.doc.product_types_locked) {
            cur_frm.set_df_property('product_types', 'read_only', true);
        } else {
            cur_frm.set_df_property('product_types', 'read_only', false);
        }
        // Show button to create deposit invoice only if:
        // - status == "Active"
        // - expiry_date is empty or in the future
        if (
            frm.doc.status === "Active" &&
            (!frm.doc.expiry_date || frappe.datetime.get_diff(frm.doc.expiry_date, frappe.datetime.nowdate()) >= 0)
        ) {
            frm.add_custom_button(__("Deposit Invoice"), function() {
                create_deposit_invoice_dialog(frm);
            }, __("Create"));
        }

        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Download Balance Sheet"), function() {

                function get_first_of_last_month() {
                    const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
                    const first_day_this_month = new Date(today.getFullYear(), today.getMonth(), 1);
                    // subtract 1 day -> last day of previous month
                    const last_day_prev_month = frappe.datetime.add_days(
                        frappe.datetime.obj_to_str(first_day_this_month), -1
                    );
                    const d = frappe.datetime.str_to_obj(last_day_prev_month);
                    return frappe.datetime.obj_to_str(new Date(d.getFullYear(), d.getMonth(), 1));
                }

                function get_last_of_last_month() {
                    const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
                    const first_day_this_month = new Date(today.getFullYear(), today.getMonth(), 1);
                    // subtract 1 day -> last day of previous month
                    return frappe.datetime.add_days(
                        frappe.datetime.obj_to_str(first_day_this_month), -1
                    );
                }

                const default_from = get_first_of_last_month();
                const default_to   = get_last_of_last_month();

                const d = new frappe.ui.Dialog({
                    'title': __("Download Balance Sheet"),
                    'fields': [
                        {
                            'fieldname': "from_date",
                            'label': __("From Date"),
                            'fieldtype': "Date",
                            'default': default_from,
                            'reqd': 1
                        },
                        {
                            'fieldname': "to_date",
                            'label': __("To Date"),
                            'fieldtype': "Date",
                            'default': default_to,
                            'reqd': 1
                        }
                    ],
                    'primary_action_label': __("Download"),
                    'primary_action'(values) {

                        const url =
                            "/api/method/microsynth.microsynth.report.customer_credits.customer_credits.download_balance_sheet_pdf"
                            + "?credit_account_id=" + encodeURIComponent(frm.doc.name)
                            + "&from_date=" + encodeURIComponent(values.from_date)
                            + "&to_date=" + encodeURIComponent(values.to_date);

                        const w = window.open(frappe.urllib.get_full_url(url), "_blank");

                        if (!w) {
                            frappe.msgprint(__("Please enable pop-ups"));
                        }
                        d.hide();
                    },
                    'secondary_action_label': __("Close")
                });
                d.show();
            });
        }
    }
});

/**
 * Opens a dialog for creating a Deposit Invoice linked to this Credit Account.
 */
function create_deposit_invoice_dialog(frm) {
    const d = new frappe.ui.Dialog({
        'title': __("Create Deposit Invoice"),
        'fields': [
            {
                fieldtype: "Currency",
                fieldname: "amount",
                label: __("Amount"),
                reqd: 1,
                description: __("Enter a positive deposit amount."),
            },
            {
                fieldtype: "Read Only",
                fieldname: "currency",
                label: __("Currency"),
                default: frm.doc.currency || "",
            },
            {
                fieldtype: "Data",
                fieldname: "override_item_name",
                label: __("Override Item Name"),
                description: __("Optional custom item description. Default: 'Primers and Sequencing'"),
            }
        ],
        'primary_action_label': __("Create"),
        primary_action(values) {
            if (!values.amount || values.amount <= 0) {
                frappe.msgprint(__("Please enter a positive amount."));
                return;
            }
            frappe.call({
                'method': "microsynth.microsynth.webshop.create_deposit_invoice",
                'args': {
                    'webshop_account': frm.doc.contact_person,
                    'account_id': frm.doc.name,
                    'amount': values.amount,
                    'currency': frm.doc.currency,
                    'description': values.override_item_name || '',
                    'company': frm.doc.company,
                    'customer': frm.doc.customer,
                    'customer_order_number': "",
                    'transmit_invoice': false
                },
                'freeze': true,
                'freeze_message': __("Creating Deposit Invoice..."),
                callback: function(r) {
                    d.hide();
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            'message': __("Deposit Invoice {0} created successfully.", [r.message.reference]),
                            'indicator': "green"
                        });
                        frappe.set_route("Form", "Sales Invoice", r.message.reference);
                    } else {
                        frappe.msgprint({
                            'title': __("Error"),
                            'indicator': "red",
                            'message': (r.message && r.message.message) || __("Failed to create deposit invoice.")
                        });
                    }
                }
            });
        },
        'secondary_action_label': __("Cancel"),
        secondary_action() {
            return;
        }
    });
    d.show();
}
