/* Custom script extension for Item */

frappe.ui.form.on('Item', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            cur_frm.set_value('is_stock_item', false);
            cur_frm.set_value('include_item_in_manufacturing', false);
        }
        if (frm.doc.__islocal && frm.doc.item_group && frm.doc.item_group == 'Purchasing') {
            cur_frm.set_value('is_stock_item', true);
        }
    }
});
