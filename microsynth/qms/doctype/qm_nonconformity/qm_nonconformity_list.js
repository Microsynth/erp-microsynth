// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


// render
frappe.listview_settings['QM Nonconformity'] = {
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "red",  /* note: all document status draft are overruled by the core to red/draft */
            "Created": "orange",
            "Classified": "yellow",
            "Investigation": "purple",
            "Planning": "lightblue",
            "Implementation": "blue",
            "Completed": "green",
            "Closed": "black",  // alternative: darkgrey or grey
        };
        return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
    }
};
