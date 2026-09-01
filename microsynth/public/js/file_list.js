frappe.listview_settings['File'] = {
    'refresh': function(listview) {
        // access protection: user shall not go to the file manager
        if (!frappe.user.has_role("System Manager")) {
            window.location.replace("/app");
        }
    }
};
    
