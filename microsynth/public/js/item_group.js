/* Custom script extension for Item Group */

frappe.ui.form.on('Item Group', {
    after_save(frm) {
        frappe.call({
            "method": "microsynth.microsynth.utils.apply_item_group_defaults",
            "args": {
                "item_group": frm.doc.name
            }
        });
    }
});