frappe.ui.form.on('File', {
    refresh(frm) {
        // access protection: user shall not go to the file manager
        if (!frappe.user.has_role("System Manager")) {
            window.location.replace("/desk");
        }
    }
})
