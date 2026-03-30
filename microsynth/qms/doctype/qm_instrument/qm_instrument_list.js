frappe.listview_settings['QM Instrument'] = {
    get_indicator: function(doc) {
        if (doc.status === "Unapproved") {
            return [__("Unapproved"), "orange", "status,=,Unapproved"];
        } else if (doc.status === "Active") {
            return [__("Active"), "green", "status,=,Active"];
        } else if (doc.status === "Blocked") {
            return [__("Blocked"), "red", "status,=,Blocked"];
        } else if (doc.status === "Decommissioned") {
            return [__("Decommissioned"), "darkgrey", "status,=,Decommissioned"];
        } else if (doc.status === "Disposed") {
            return [__("Disposed"), "black", "status,=,Disposed"];
        } else {
            return [__(doc.status), "blue", "status,=," + doc.status];
        }
    },
    onload: function(listview) {
        add_clear_button();
    }
};
