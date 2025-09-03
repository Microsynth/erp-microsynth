frappe.ui.form.on('Job Offer', {
    refresh: function(frm) {
        // Remove the core "Create Employee" button
        frm.clear_custom_buttons();

        // Add your own "Create Employee" button
        if (frm.doc.status === 'Accepted' && !frm.doc.__islocal && frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Create Employee'), function() {
                frappe.model.open_mapped_doc({
                    method: "microsynth.microsynth.hr.map_job_applicant_to_employee",
                    frm: frm
                });
            });
        }
    }
});
