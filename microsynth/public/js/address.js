frappe.ui.form.on('Address', {
    after_save(frm) {
        if ((frm.doc.links) && (frm.doc.links.length > 0) && (frm.doc.links[0].link_doctype === "Customer")) {
            frappe.call({
                "method":"microsynth.microsynth.utils.configure_customer",
                "args": {
                    "customer": frm.doc.links[0].link_name
                }
            });
        }
    }
});