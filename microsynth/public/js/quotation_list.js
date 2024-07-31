// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['Quotation'] = {
    add_fields: ["customer_name", "base_grand_total", "status",
        "company", "currency", 'valid_till'],

    onload: function(listview) {
        if (listview.page.fields_dict.quotation_to) {
            listview.page.fields_dict.quotation_to.get_query = function() {
                return {
                    "filters": {
                        "name": ["in", ["Customer", "Lead"]],
                    }
                };
            };
        }
        add_clear_button();
    },

    get_indicator: function(doc) {
        if(doc.status==="Open") {
            if (doc.valid_till && doc.valid_till < frappe.datetime.nowdate()) {
                return [__("Expired"), "darkgrey", "valid_till,<," + frappe.datetime.nowdate()];
            } else {
                return [__("Open"), "orange", "status,=,Open"];
            }
        } else if(doc.status==="Ordered") {
            return [__("Ordered"), "green", "status,=,Ordered"];
        } else if(doc.status==="Lost") {
            return [__("Lost"), "darkgrey", "status,=,Lost"];
        }
    }
};
