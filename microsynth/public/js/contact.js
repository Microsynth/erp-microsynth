/* Custom script extension for Contact */
frappe.ui.form.on('Contact', {
    before_save(frm) {		
        update_address_links(frm);				
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