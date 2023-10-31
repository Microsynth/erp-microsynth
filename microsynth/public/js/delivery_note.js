/* Custom script extension for Delivery Note */
frappe.ui.form.on('Delivery Note', {
    refresh(frm) {
        prepare_naming_series(frm);				// common function
        
        hide_in_words();
        
        if (frm.doc.__islocal) {
            setTimeout(function () {
                check_prevdoc_rates(cur_frm);
            }, 500);
        }
    },
    company(frm) {
        set_naming_series(frm);					// common function
    }
});

frappe.ui.form.on('Delivery Note Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});

function check_prevdoc_rates(frm) {
    var so_details = [];
    for (var i = 0; i < frm.doc.items.length; i++) {
        so_details.push(frm.doc.items[i].so_detail);
    }
    
    frappe.call({
        'method': 'microsynth.microsynth.utils.fetch_price_list_rates_from_prevdoc',
        'args': {
            'prevdoc_doctype': "Delivery Note",
            'prev_items': so_details
        },
        'callback': function(response) {
            var prevdoc_price_list_rates = response.message;
            for (var i = 0; i < cur_frm.doc.items.length; i++) {
                frappe.model.set_value(cur_frm.doc.items[i].doctype, cur_frm.doc.items[i].name, "price_list_rate", prevdoc_price_list_rates[i]);
            }
        }
    });
}
