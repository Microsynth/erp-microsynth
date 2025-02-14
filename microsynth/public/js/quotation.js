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
                if (customer.default_price_list) {cur_frm.set_value("selling_price_list", customer.default_price_list); }
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
                        if ((cur_frm.doc.service_specification) && (!cur_frm.doc.service_specification.includes(item.service_specification))) {
                            cur_frm.set_value("service_specification", cur_frm.doc.service_specification /* + "<p>&nbsp;</p>" */ + item.service_specification);
                        } else {
                            cur_frm.set_value("service_specification", "<h3>Service Description</h3>" + item.service_specification);
                        }
                    }
                }
            }
        });
    }
}
