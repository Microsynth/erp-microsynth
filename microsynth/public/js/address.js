frappe.ui.form.on('Address', {
    refresh(frm) {
        // set Address source
        if (frm.doc.__islocal) {
            cur_frm.set_value("address_source", "Manual");
        }
        // show a banner if source = Punchout
        if (frm.doc.address_source && frm.doc.address_source == "Punchout") {
            frm.dashboard.add_comment( __("Punchout Address! Please do <b>not</b> edit."), 'red', true);
        }
        // lock all fields if source = Punchout
        if (!frappe.user.has_role("System Manager") && (frm.doc.address_source && frm.doc.address_source == "Punchout")) {
            cur_frm.set_df_property('address_title', 'read_only', true);
            cur_frm.set_df_property('address_type', 'read_only', true);
            cur_frm.set_df_property('overwrite_company', 'read_only', true);
            cur_frm.set_df_property('address_line1', 'read_only', true);
            cur_frm.set_df_property('address_line2', 'read_only', true);
            cur_frm.set_df_property('pincode', 'read_only', true);
            cur_frm.set_df_property('city', 'read_only', true);
            cur_frm.set_df_property('state', 'read_only', true);
            cur_frm.set_df_property('country', 'read_only', true);
            cur_frm.set_df_property('tax_category', 'read_only', true);
            cur_frm.set_df_property('is_primary_address', 'read_only', true);
            cur_frm.set_df_property('is_shipping_address', 'read_only', true);
            cur_frm.set_df_property('disabled', 'read_only', true);
            cur_frm.set_df_property('customer_address_id', 'read_only', true);
            cur_frm.set_df_property('is_your_company_address', 'read_only', true);
            cur_frm.set_df_property('links', 'read_only', true);
            cur_frm.set_df_property('branch_gln', 'read_only', true);
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
