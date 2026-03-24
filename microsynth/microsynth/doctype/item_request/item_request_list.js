frappe.listview_settings['Item Request'] = {
    get_indicator: function(doc) {
        if(doc.status=="Pending") {
            return [__("Pending"), "orange", "status,=,Pending"];
        } else if(doc.status=="Rejected") {
            return [__("Rejected"), "red", "status,=,Rejected"];
        } else if(doc.docstatus==2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        } else if(doc.status=="Done") {
            return [__("Done"), "green", "status,=,Done"];
        } else if(doc.docstatus==0) {
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
