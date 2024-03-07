// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Standing Quotation', {
    refresh(frm) {
        cur_frm.fields_dict['address'].get_query = function(doc) {
            return {
                filters: {
                    'link_doctype': 'Customer',
                    'link_name': frm.doc.customer
                }
            }
        }
        cur_frm.fields_dict['contact'].get_query = function(doc) {
            return {
                filters: {
                    'link_doctype': 'Customer',
                    'link_name': frm.doc.customer
                }
            }
        }
    
        if ((!frm.doc.__islocal) && (frm.doc.price_list)) {
            frm.add_custom_button(__("Price List"), function() {
                frappe.set_route("query-report", "Pricing Configurator", {'price_list': frm.doc.price_list});
            });
        }
        
        // populate from price list discount items
        if (frm.doc.price_list) {
            frm.add_custom_button(__("Populate Discount Items"), function() {
                frappe.call({
                    'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.get_discount_items",
                    'args': {
                        "price_list": frm.doc.price_list
                    },
                    'callback': function(response) {
                        var items = response.message;
                        for (var i = 0; i < items.length; i++) {
                            var child = cur_frm.add_child('items');
                            frappe.model.set_value(child.doctype, child.name, 'item_code', items[i].item_code);
                            frappe.model.set_value(child.doctype, child.name, 'item_name', items[i].item_name);
                            frappe.model.set_value(child.doctype, child.name, 'qty', items[i].qty);
                        }
                        cur_frm.refresh_field('items');
                    }
                });
            });
        }

        // Initialize the terms
        if ((frm.doc.__islocal) && (frm.doc.terms_template)) {
            set_terms(frm);
        }
    },
    on_submit(frm) {
        setTimeout(function () {cur_frm.reload_doc();}, 5000);
    },
    price_list(frm) {
        if (frm.doc.price_list) {
            frappe.call({
               'method': "frappe.client.get",
               'args': {
                    "doctype": "Price List",
                    "name": frm.doc.price_list
               },
               'callback': function(response) {
                    var price_list = response.message;
                    if (price_list) {
                       cur_frm.set_value("general_discount", price_list.general_discount);
                    }
               }
            });
        }
    },
    terms_template(frm) {
        set_terms(frm);
    }
});


function set_terms(frm) {
    if (frm.doc.terms_template) {
        frappe.call({
            'method': "frappe.client.get",
            'args': {
                 "doctype": "Terms and Conditions",
                 "name": frm.doc.terms_template
            },
            'callback': function(response) {
                 var terms_and_conditions = response.message;
                 if (terms_and_conditions) {
                    cur_frm.set_value("terms", terms_and_conditions.terms);
                 }
            }
         });
    }
}