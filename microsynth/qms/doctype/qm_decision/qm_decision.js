// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Decision', {
    refresh: function(frm) {
        cur_frm.page.clear_primary_action();
        cur_frm.page.clear_secondary_action();
    }
});
