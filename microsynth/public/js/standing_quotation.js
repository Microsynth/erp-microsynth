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
        
        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0)) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            });
        }
    },
});
