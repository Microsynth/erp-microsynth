// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['QM Impact Assessment'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "red",  /* note: all document status draft are overruled by the core to red/draft */
            "Requested": "orange",
            "Completed": "green",
            "Cancelled": "red"
        };
        return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
    }
};
