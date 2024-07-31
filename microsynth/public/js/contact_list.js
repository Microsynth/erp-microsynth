// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['Contact'] = {
    add_fields: ["image"],
    onload: function(doc) {
        add_clear_button();
    }
};
