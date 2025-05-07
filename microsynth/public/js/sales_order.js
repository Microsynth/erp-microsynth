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

        if (frm.doc.docstatus === 2 && frm.doc.web_order_id) {
            frm.add_custom_button(__("Search valid version"), function() {
                frappe.set_route("List", "Sales Order", {"web_order_id": frm.doc.web_order_id, "docstatus": 1});
            });
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
            "po_no": frm.doc.po_no
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
