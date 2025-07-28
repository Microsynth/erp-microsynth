frappe.ui.form.on('Job Applicant', {
    before_save(frm) {
        let first_name = frm.doc.first_name || "";
        let last_name = frm.doc.last_name || "";
        let spacer = "";
        if (frm.doc.last_name) {spacer = " ";}
        // set full name
        cur_frm.set_value("applicant_name", (first_name + spacer + last_name));
    },
    address: function(frm) {
        if (frm.doc.address) {
            frappe.db.get_doc('Address', frm.doc.address)
                .then(address => {
                    const display = `
${address.address_line1 || ''}
${address.pincode || ''} ${address.city || ''}
${address.country || ''}
                    `.trim();
                    frm.set_value("address_display", display);
                });
        } else {
            frm.set_value("address_display", '');
        }
    }
})


frappe.ui.form.on('Job Applicant Assessment', {
    // This triggers when a new row is added to the child table
    assessments_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if(!row.assessor) {
            row.assessor = frappe.session.user;
            frm.refresh_field('assessments');
        }
    }
});
