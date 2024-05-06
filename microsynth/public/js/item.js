/* Custom script extension for Item */

frappe.ui.form.on('Item', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            cur_frm.set_value('is_stock_item', false);
            cur_frm.set_value('include_item_in_manufacturing', false);
        }
    },
    
    before_save(frm) {
        // Set Item Defaults according to the Item Group when creating an item
        if (frm.doc.__islocal) {
            frappe.call({
                "method": "microsynth.microsynth.utils.overwrite_item_defaults",
                "args": {
                    "item": frm.doc.name
                }
            });
        }
    }
});
