// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
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
           frappe.set_route("List", "Customer", {"default_price_list": frappe.query_report.filters[0].value });
        });
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
        });
    }
};

function populate_from_reference() {
    frappe.call({
        'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.populate_from_reference",
        'args':{
            'price_list': frappe.query_report.filters[0].value,
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
        frappe.call({
            'method': "microsynth.microsynth.report.pricing_configurator.pricing_configurator.populate_with_factor",
            'args':{
                'price_list': frappe.query_report.filters[0].value,
                'item_group': frappe.query_report.filters[1].value,
                'factor': values.factor
            },
            'callback': function(r)
            {
                frappe.query_report.refresh();
            }
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
