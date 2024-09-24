/* Custom script extension for Delivery Note */
frappe.ui.form.on('Delivery Note', {
    refresh(frm) {
        locals.prevdoc_checked = false;
        prepare_naming_series(frm);             // common function

        // show a warning if is_punchout
        if (frm.doc.docstatus == 0 && frm.doc.is_punchout == 1) {
            frm.dashboard.add_comment( __("Punchout Order! Please do <b>not</b> edit the Items."), 'red', true);
        }
        
        hide_in_words();

        var time_out = 500;
        if (frm.doc.items){
            time_out += frm.doc.items.length * 100;
        }
        if (frm.doc.__islocal) {
            setTimeout(function () {
                check_prevdoc_rates(cur_frm);
            }, time_out);
        }

        // remove Menu > Email if document is not valid
        if (frm.doc.docstatus != 1) {
            var target ="span[data-label='" + __("Email") + "']";
            $(target).parent().parent().remove();
        }
        
        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
			frm.add_custom_button(__("Force Cancel"), function() {
				force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
			});
		}
    },
    company(frm) {
        set_naming_series(frm);                 // common function
    },
    before_save(frm) {
        set_export_category(frm);
    },
    validate(frm) {
        if (!locals.prevdoc_checked && frm.doc.__islocal) {
            frappe.msgprint( __("Please be patient, prices are being checked..."), __("Validation") );
            frappe.validated=false;
        }
    }
});


frappe.ui.form.on('Delivery Note Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});


function set_export_category(frm) {
    frappe.call({
        'method': "microsynth.microsynth.utils.get_export_category",
        'args': { 
            'address_name': frm.doc.shipping_address_name
        },
        'async': false,
        'callback': function(response)
        {
            if(!frm.doc.export_category) {  // only set export_category if field is empty
                cur_frm.set_value("export_category", response.message);
                frappe.show_alert("Set Export Category to " + response.message);
            }
        }
    });
}


function check_prevdoc_rates(frm) {
    var so_details = [];
    if (frm.doc.items) {
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
                    if(prevdoc_price_list_rates[i] != null) {
                        frappe.model.set_value(cur_frm.doc.items[i].doctype, cur_frm.doc.items[i].name, "price_list_rate", prevdoc_price_list_rates[i]);
                    }
                }
                locals.prevdoc_checked = true;
            }
        });
    } else {
        locals.prevdoc_checked = true;
    }
}
