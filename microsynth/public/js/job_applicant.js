frappe.ui.form.on('Job Applicant', {
    before_save(frm) {
        let first_name = frm.doc.first_name || "";
        let last_name = frm.doc.last_name || "";
        let spacer = "";
        if (frm.doc.last_name) {spacer = " ";}
        // set full name
        cur_frm.set_value("applicant_name", (first_name + spacer + last_name));
    }
})
