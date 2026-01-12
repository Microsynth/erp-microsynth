/* Custom script extension for Material Request */
frappe.ui.form.on('Material Request', {
    onload(frm) {
        // remove empty row from items table
        if (frm.doc.__islocal && frm.doc.items && frm.doc.items.length === 1 && !frm.doc.items[0].item_code) {
            frm.clear_table('items');
            frm.refresh_field('items');
        }
    },
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }

        setTimeout(function () {
            cur_frm.fields_dict.items.grid.get_field('item_code').get_query =
                function(frm, dt, dn) {
                    return {
                        query: "microsynth.microsynth.filters.find_purchasing_items",
                        filters: {
                            "item_group": 'Purchasing',
                            "disabled": 0
                        }
                    };
                };
        }, 1000);

        hide_in_words();
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
    }
});
