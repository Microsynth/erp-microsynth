frappe.ui.form.on('Standing Quotation', {
    refresh(frm){
        // remove Menu > Email if document is not valid
        if (frm.doc.docstatus != 1) {
            var target ="span[data-label='" + __("Email") + "']";
            $(target).parent().parent().remove();
        }

        // Display internal Item notes in a green banner if the Quotation is in Draft status
        if (frm.doc.docstatus == 0 && frm.doc.items.length > 0) {
            var dashboard_comment_color = 'green';
            for (var i = 0; i < frm.doc.items.length; i++) {
                if (frm.doc.items[i].item_code) {
                    frappe.call({
                        'method': "frappe.client.get",
                        'args': {
                            "doctype": "Item",
                            "name": frm.doc.items[i].item_code
                        },
                        'callback': function(response) {
                            var item = response.message;
                            if (item.internal_note) {
                                cur_frm.dashboard.add_comment("<b>" + item.item_code + "</b>: " + item.internal_note, dashboard_comment_color, true);
                            }
                        }
                    });
                }
            }
        }

        // add button "Populate Shipping Items"
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
            frm.add_custom_button(__("Populate Shipping Items"), function() {
                populate_shipping_items();
            });
        }
        
        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            });
        }
    },
});


function populate_shipping_items() {
    frappe.call({
        'method': "microsynth.microsynth.webshop.get_shipping_items",
        'args': {
            "customer_id": cur_frm.doc.customer
        },
        'callback': function(response) {
            var shipping_items = response.message.shipping_items;
            for (var i = 0; i < shipping_items.length; i++) {
                var child = cur_frm.add_child('shipping_items');
                frappe.model.set_value(child.doctype, child.name, 'item', shipping_items[i].item);
                frappe.model.set_value(child.doctype, child.name, 'item_name', shipping_items[i].item_name);
                frappe.model.set_value(child.doctype, child.name, 'qty', shipping_items[i].qty);
                frappe.model.set_value(child.doctype, child.name, 'rate', shipping_items[i].rate);
                frappe.model.set_value(child.doctype, child.name, 'threshold', shipping_items[i].threshold);
                frappe.model.set_value(child.doctype, child.name, 'preferred_express', shipping_items[i].preferred_express);
            }
            cur_frm.refresh_field('shipping_items');
        }
    });
}
