// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Pricing Configurator"] = {
    "filters": [
        {
            "fieldname":"price_list",
            "label": __("Price List"),
            "fieldtype": "Link",
            "options": "Price List",
            "reqd": 1
        },
        {
            "fieldname":"item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname":"discounts",
            "label": __("Discount"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        if (frappe.user.has_role("Sales Manager")) {
            report.page.add_inner_button(__('Change General Discount'), function () {
                change_general_discount();
            });
        }
        report.page.add_inner_button(__('Clean price list'), function () {
            clean_price_list();
        });        
        report.page.add_inner_button(__('Populate from reference'), function () {
           populate_from_reference();
        });
        report.page.add_inner_button(__('Populate with factor'), function () {
           populate_with_factor();
        });
        report.page.add_inner_button(__('Price List'), function () {
            frappe.set_route("Form", "Price List", frappe.query_report.filters[0].value);
        });
        report.page.add_inner_button(__('Customers'), function () {
           frappe.set_route("List", "Customer", {"default_price_list": frappe.query_report.filters[0].value, "disabled": 0});
        });
        if (!locals.double_click_handler) {
            locals.double_click_handler = true;
            
            // add event listener for double clicks to move up
            cur_page.container.addEventListener("dblclick", function(event) {
                var row = event.delegatedTarget.getAttribute("data-row-index");
                var column = event.delegatedTarget.getAttribute("data-col-index");
                if (parseInt(column) === 7) {
                    // fetch value
                    var value = 1;
                    if ((event.delegatedTarget.innerText) && (event.delegatedTarget.innerText.length > 0)) {
                        value = parseFloat(event.delegatedTarget.innerText);
                    }
                    // get price list fom filters
                    var price_list = null;
                    for (var i = 0; i < frappe.query_report.filters.length; i++) {
                        if (frappe.query_report.filters[i].fieldname == "price_list") {
                            price_list = frappe.query_report.filters[i].value;
                        }
                    }
                    // get the quantity from data
                    var qty = frappe.query_report.data[row].qty
                    // get item_code from data
                    var item_code = frappe.query_report.data[row].item_code;
                    edit_cell(item_code, price_list, qty, value);
                }
                else if (parseInt(column) === 8 ) {
                    // fetch value
                    var discount = 1;
                    if ((event.delegatedTarget.innerText) && (event.delegatedTarget.innerText.length > 0)) {
                        discount = parseFloat(event.delegatedTarget.innerText);
                    }
                    // get price list fom filters
                    var price_list = null;
                    for (var i = 0; i < frappe.query_report.filters.length; i++) {
                        if (frappe.query_report.filters[i].fieldname == "price_list") {
                            price_list = frappe.query_report.filters[i].value;
                        }
                    }
                    // get the quantity from data
                    var qty = frappe.query_report.data[row].qty
                    // get item_code from data
                    var item_code = frappe.query_report.data[row].item_code;
                    var reference_rate = frappe.query_report.data[row].reference_rate;
                    edit_discount_cell(item_code, price_list, qty, discount, reference_rate);
                }
            });
        }
    }
};


function change_general_discount(){
    frappe.prompt([
        {'fieldname': 'new_general_discount', 'fieldtype': 'Float', 'label': __('New General Discount'), 'reqd': 1}  
    ],
    function(values){
        frappe.confirm('Are you sure you want to proceed?<br>All <b>prices</b> with the original general discount <b>will be changed</b> to the new general discount (' + values.new_general_discount + '%).<br><br><b>Please be patient</b>, the process may take several minutes. The table is automatically reloaded after completion.',
            () => {
                if (values.new_general_discount > 100) {
                    frappe.show_alert('New general discount has to be <= 100. Otherwise prices would get negative.');
                    return;
                }
                frappe.call({
                    'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.change_general_discount",
                    'args':{
                        'price_list_name': frappe.query_report.filters[0].value,
                        'new_general_discount': values.new_general_discount,
                        'user': frappe.session.user
                    },
                    'callback': function(response)
                    {
                        frappe.query_report.refresh();
                        if (response.message.length > 0) {
                            // show message box with return value from python function (contains errors about item prices not present on the reference price list)
                            frappe.msgprint({
                                title: __('Warning'),
                                indicator: 'orange',
                                message: 'The discount could not be changed for the following items:<br><br>' + response.message
                            });
                        } else {
                            frappe.show_alert('New general discount has been applied.');
                        }
                    }
                });
            }, () => {
                frappe.show_alert('No new general discount applied');
            });        
    },
    __('Change General Discount'),
    __('OK')
    );
}


function clean_price_list(){
    frappe.call({
        'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.clean_price_list",
        'args':{
            'price_list': frappe.query_report.filters[0].value,
            'user': frappe.session.user
        },
        'callback': function(r)
        {
            frappe.query_report.refresh();
        }
    });
}


function populate_from_reference() {
    frappe.call({
        'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.populate_from_reference",
        'args':{
            'price_list': frappe.query_report.filters[0].value,
            'user': frappe.session.user,
            'item_group': frappe.query_report.filters[1].value
        },
        'callback': function(r)
        {
            frappe.query_report.refresh();
        }
    });
}


function populate_with_factor() {
    frappe.prompt([
        {'fieldname': 'factor', 'fieldtype': 'Float', 'label': __('Factor'), 'default': 1.0, 'reqd': 1}  
    ],
    function(values){
        frappe.confirm('Are you sure you want to proceed?<br><b>All prices</b> will be <b>overwritten</b> with a rate derived from the reference list multiplied with the given factor.',
            () => {
                frappe.call({
                    'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.populate_with_factor",
                    'args':{
                        'price_list': frappe.query_report.filters[0].value,
                        'user': frappe.session.user,
                        'item_group': frappe.query_report.filters[1].value,
                        'factor': values.factor
                    },
                    'callback': function(r)
                    {
                        frappe.query_report.refresh();
                    }
                });
            }, () => {
                frappe.show_alert('No prices changed');
            });        
    },
    __('Populate with factor'),
    __('OK')
    );
}


function edit_cell(item_code, price_list, qty, value) {
    var d = new frappe.ui.Dialog({
        'fields': [
            {'fieldname': 'price_list', 'fieldtype': 'Link', 'options': "Price List", 'label': __('Price List'), 'read_only': 1, 'default': price_list},
            {'fieldname': 'item_code', 'fieldtype': 'Link', 'options': "Item", 'label': __('Item'), 'read_only': 1, 'default': item_code},
            {'fieldname': 'qty', 'fieldtype': 'Float', 'precision': 2, 'label': __('Quantity'), 'read_only': 1, 'default': qty},
            {'fieldname': 'rate', 'fieldtype': 'Float', 'precision': 2, 'label': __('Rate'), 'reqd': 1, 'default': value}
        ],
        'primary_action': function(){
            d.hide();
            var values = d.get_values();
            frappe.call({
                'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.set_rate",
                'args':{
                    'item_code': values.item_code,
                    'price_list': values.price_list,
                    'qty': values.qty,
                    'rate': values.rate
                },
                'callback': function(r)
                {
                    frappe.query_report.refresh();
                }
            });
        },
        'primary_action_label': __('Change'),
        'title': __('Change rate')
    });
    d.show();
}


function edit_discount_cell(item_code, price_list, qty, discount, reference_rate) {
    var d = new frappe.ui.Dialog({
        'fields': [
            {'fieldname': 'price_list', 'fieldtype': 'Link', 'options': "Price List", 'label': __('Price List'), 'read_only': 1, 'default': price_list},
            {'fieldname': 'item_code', 'fieldtype': 'Link', 'options': "Item", 'label': __('Item'), 'read_only': 1, 'default': item_code},
            {'fieldname': 'qty', 'fieldtype': 'Float', 'precision': 2, 'label': __('Quantity'), 'read_only': 1, 'default': qty},
            {'fieldname': 'rate', 'fieldtype': 'Float', 'precision': 2, 'label': __('Reference Rate'), 'read_only': 1, 'default': reference_rate},
            {'fieldname': 'discount', 'fieldtype': 'Float', 'precision': 2, 'label': __('Discount'), 'reqd': 1, 'default': discount}
        ],
        'primary_action': function(){
            d.hide();
            var values = d.get_values();
            var rate = reference_rate  * (1 - values.discount/100)
            frappe.call({
                'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.set_rate",
                'args':{
                    'item_code': values.item_code,
                    'price_list': values.price_list,
                    'qty': values.qty,
                    'rate': rate
                },
                'callback': function(r)
                {
                    frappe.query_report.refresh();
                }
            });
        },
        'primary_action_label': __('Change'),
        'title': __('Change rate')
    });
    d.show();
}