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
        }
    ],
    "onload": (report) => {
        report.page.add_inner_button(__('Populate from reference'), function () {
           populate_from_reference();
        })
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
