// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['Customer'] = {
    add_fields: ["customer_name", "territory", "customer_group", "customer_type", "image"],
    onload: function(doc) {
        add_clear_button();
    }
};
