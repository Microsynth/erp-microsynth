frappe.pages['invoice_entry'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Invoice Entry',
        single_column: true
    });

    frappe.invoice_entry.make(page);
    frappe.invoice_entry.run(page);

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
    run: function(page) { 
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
        let html = "";
        document.getElementById("pi_drafts_view").innerHTML = "";
        for (let i = 0; i < purchase_invoice_drafts.length; i++) {
            html += purchase_invoice_drafts[i].html;
        }
        // insert content
        document.getElementById("pi_drafts_view").innerHTML = html;
        
        for (let i = 0; i < purchase_invoice_drafts.length; i++) {
            frappe.invoice_entry.create_fields(purchase_invoice_drafts[i]);
        }
    },
    create_fields: function(purchase_invoice) {
        // supplier link field
        let supplier_fieldname = "supplier_" + purchase_invoice.name;
        let supplier_field = document.getElementById(supplier_fieldname);
        let supplier_link_field = frappe.ui.form.make_control({
            'parent': supplier_field,
            'df': {
                'fieldtype': "Link",
                'fieldname': supplier_fieldname,
                'options': 'Supplier',
                'placeholder': __("Supplier")
            }
        });
        supplier_link_field.refresh();
        supplier_link_field.set_value(purchase_invoice.supplier);
        
        // posting date
        let posting_date_fieldname = "posting_date_" + purchase_invoice.name;
        let posting_date_field = document.getElementById(posting_date_fieldname);
        let posting_date_link_field = frappe.ui.form.make_control({
            'parent': posting_date_field,
            'df': {
                'fieldtype': "Date",
                'fieldname': posting_date_fieldname,
                'placeholder': __("Posting Date"),
                'default': purchase_invoice.posting_date
            }
        });
        posting_date_link_field.refresh();
        posting_date_link_field.set_value(purchase_invoice.posting_date);
    }

}
