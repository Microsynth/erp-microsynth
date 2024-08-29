frappe.pages['invoice_entry'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Invoice Entry',
		single_column: true
	});

	frappe.invoice_entry.make(page);
    frappe.invoice_entry.run();

    // add the application reference
    frappe.breadcrumbs.add("Microsynth");
}


frappe.invoice_entry = {
    start: 0,
    make: function(page) {
        var me = frappe.invoice_entry;
        me.page = page;
        me.body = $('<div></div>').appendTo(me.page.main);
        var data = "";
        $(frappe.render_template('invoice_entry', data)).appendTo(me.body);
    },
    run: function() { 
        frappe.invoice_entry.get_purchase_invoice_drafts();
    },
    get_purchase_invoice_drafts: function() {
        frappe.call({
            'method': 'microsynth.microsynth.page.invoice_entry.invoice_entry.get_purchase_invoice_drafts',
            'callback': function(r) {
                var purchase_invoice_drafts = r.message;
                frappe.invoice_entry.display_purchase_invoice_drafts(purchase_invoice_drafts);
            }
        });
    },
    display_purchase_invoice_drafts: function(purchase_invoice_drafts) {
        // create rows
        var html = "";
        document.getElementById("pi_drafts_view").innerHTML = "";
        for (var i = 0; i < purchase_invoice_drafts.length; i++) {
            html += purchase_invoice_drafts[i].html;
        }
        // insert content
        document.getElementById("pi_drafts_view").innerHTML = html;
    }
}