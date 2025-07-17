/* Custom script extension for Purchase Order */
frappe.ui.form.on('Purchase Order', {
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
                            "supplier": cur_frm.doc.supplier,
                            "item_group": 'Purchasing',
                            "disabled": 0
                        }
                    };
                };
        }, 1000);

        hide_in_words();
    },
    onload(frm) {
        if (!locals.inbound_freight_item) {
            frappe.call({
                'method': 'frappe.client.get',
                'args': {
                    doctype: 'Microsynth Settings'
                },
                callback: function(r) {
                    if (r.message && r.message.inbound_freight_item) {
                        locals.inbound_freight_item = r.message.inbound_freight_item;
                    }
                }
            });
        }
    },
    before_save: function(frm) {
        var freight_item_code = locals.inbound_freight_item;

        if (!freight_item_code) return;

        var already_exists = frm.doc.items.some(function(item) {
            return item.item_code === freight_item_code;
        });

        if (!already_exists) {
            frm.add_child('items', {
                'item_code': freight_item_code,
                'qty': 1,
                'rate': 0,
                'base_rate': 0,
                'amount': 0,
                'base_amount': 0,
                'conversion_factor': 1,
                'schedule_date': frm.doc.schedule_date || frappe.datetime.get_today(),
                'uom': 'Pcs',
                'item_name': 'Inbound Freight',
                'description': 'Inbound Freight Cost'
            });
            frm.refresh_field('items');
        }
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
    }
});
