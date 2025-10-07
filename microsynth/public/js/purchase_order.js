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
                'method': 'microsynth.microsynth.purchasing.get_inbound_freight_item',
                'callback': function(r) {
                    if (r.message) {
                        locals.inbound_freight_item = r.message;
                    }
                }
            });
        }
    },
    before_save: function(frm) {
        add_freight_item(frm);
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
        get_supplier_tax_template(frm);
    },
    supplier(frm) {
        get_supplier_tax_template(frm);
    }
});


function add_freight_item(frm) {
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
}


function get_supplier_tax_template(frm) {
    if ((frm.doc.company) && (frm.doc.supplier)) {
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.get_purchase_tax_template',
            'args': {
                'supplier': frm.doc.supplier,
                'company': frm.doc.company
            },
            'callback': function(response) {
                if (response.message) {
                    console.log("set taxes to: " + response.message);
                    setTimeout(function() {
                        cur_frm.set_value("taxes_and_charges", response.message);
                    }, 500);
                }
            }
        });
    }
}
