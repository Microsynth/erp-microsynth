/* Custom script extension for Contact */
frappe.ui.form.on('Contact', {
    before_save(frm) {
        update_address_links(frm);
        
        let first_name = frm.doc.first_name || "";
        let last_name = frm.doc.last_name || "";
        let spacer = "";
        if (frm.doc.last_name) {spacer = " ";}    

        // set full name
        cur_frm.set_value("full_name", (first_name + spacer + last_name));
    }
});

function update_address_links(frm) {
    if (frm.doc.address) {
        frappe.call({
            "method":"microsynth.microsynth.utils.update_address_links_from_contact",
            "args":{
                "address_name":frm.doc.address,
                "links": (frm.doc.links || [] )
            }
        })
    }
}
