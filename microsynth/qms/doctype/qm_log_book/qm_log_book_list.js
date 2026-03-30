frappe.listview_settings['QM Log Book'] = {
    add_fields: ['status', 'docstatus'],
    get_indicator: function(doc) {
        // Cancelled
        if (doc.docstatus === 2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }
        // Submitted → OVERRIDE DEFAULT HERE
        if (doc.docstatus === 1) {
            if (doc.status === "To Review") {
                return [__("To Review"), "orange", "status,=,To Review"];
            } else if (doc.status === "Closed") {
                return [__("Closed"), "green", "status,=,Closed"];
            }
            // fallback for submitted
            return [__("Submitted"), "blue", "docstatus,=,1"];
        }
        // Draft
        if (doc.docstatus === 0) {
            return [__("Draft"), "red", "docstatus,=,0"];
        }
    },
    onload: function(listview) {
        add_clear_button();
    },
    refresh: function(listview) {
        if (frappe.user.has_role('System Manager')) return;
        // Hide the New button
        listview.page.btn_primary && listview.page.btn_primary.hide();
    }
};
