// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

// render
frappe.listview_settings['QM Computerised System'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Unapproved": "red",
            "Validated": "green",
            "Decommissioned": "darkgrey"
        };
        return [__(doc.status), status_color[doc.status], "status,=," + doc.status];
    },
    onload: function(listview) {
        add_clear_button();
    }
};
