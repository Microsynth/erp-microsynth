frappe.ui.form.on('Address', {
    refresh(frm) {
        // show a banner if source = Punchout
        if (frm.doc.source && frm.doc.source == "Punchout") {
            frm.dashboard.add_comment( __("Punchout Address! Please do <b>not</b> edit."), 'red', true);
        }
    },
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
