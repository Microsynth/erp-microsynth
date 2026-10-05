// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.listview_settings['Staff Profile'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "red",
            "To Sign": "yellow",
            "Valid": "green",
            "Archived": "darkgrey"
        };
        return [__(doc.status), status_color[doc.status] || "blue", "status,=," + doc.status];
    }
};
