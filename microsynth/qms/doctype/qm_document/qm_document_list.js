// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['QM Document'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "red",             /* note: all document status draft are overruled by the core to red/draft */
            "Created": "purple",
            "In Review": "orange",
            "Reviewed": "yellow",
            "Released": "blue",
            "Valid": "green",
            "Invalid": "darkgrey"
        };
        return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
    }
};
