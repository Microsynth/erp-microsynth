frappe.listview_settings['Item Request'] = {
    refresh: function(listview) {
        if (frappe.user.has_role('System Manager')) return;
        // Hide the New button
        listview.page.btn_primary && listview.page.btn_primary.hide();
    }
};
