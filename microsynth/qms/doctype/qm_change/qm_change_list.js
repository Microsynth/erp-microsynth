// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['QM Change'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "red",  /* note: all document status draft are overruled by the core to red/draft */
            "Created": "orange",
            "Assessment & Classification": "yellow",
            "Trial": "lightblue",
            "Planning": "blue",
            "Implementation": "purple",
            "Completed": "green",
            "Closed": "black",  // alternative: darkgrey or grey
            "Cancelled": "red"
        };
        return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
    },
    onload: function(doc) {
        add_clear_button();
    }
};
