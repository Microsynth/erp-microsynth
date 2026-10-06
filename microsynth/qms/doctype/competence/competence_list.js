// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.listview_settings['Competence'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "red",
            "Valid": "green",
            "Invalid": "darkgrey"
        };
        return [__(doc.status), status_color[doc.status] || "blue", "status,=," + doc.status];
    }
};
