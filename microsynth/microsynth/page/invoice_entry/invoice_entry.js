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
            frappe.invoice_entry.attach_save_handler(purchase_invoice_drafts[i].name);
        }
    },
    create_fields: function(purchase_invoice) {
        frappe.invoice_entry.create_field(purchase_invoice, 'Link', 'supplier', 'Supplier', 'Supplier');
        frappe.invoice_entry.create_field(purchase_invoice, 'Date', 'posting_date', 'Posting Date', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Date', 'due_date', 'Due Date', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Data', 'bill_no', 'Supplier Invoice No', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Link', 'approver', 'Approver', 'User');
        frappe.invoice_entry.create_field(purchase_invoice, 'Small Text', 'remarks', 'Remarks', '');
        frappe.invoice_entry.remove_clearfix_nodes();
    },
    create_field: function(purchase_invoice, fieldtype, field_name, placeholder, options) {
        let fieldname = field_name + "_" + purchase_invoice.name;
        let field = document.getElementById(fieldname);
        let link_field = frappe.ui.form.make_control({
            'parent': field,
            'df': {
                'fieldtype': fieldtype,
                'fieldname': fieldname,
                'options': options,
                'placeholder': __(placeholder),
                'default': purchase_invoice[fieldname]
            }
        });
        link_field.refresh();
        link_field.set_value(purchase_invoice[field_name]);
    },
    attach_save_handler: function(purchase_invoice_name) {
        let btn_save = document.getElementById("btn_save_" + purchase_invoice_name);
        btn_save.onclick = frappe.invoice_entry.save_document.bind(this, purchase_invoice_name);
    },
    save_document: function(purchase_invoice_name) {
        let doc = {
            'name': purchase_invoice_name,
            'supplier': document.querySelectorAll("input[data-fieldname='supplier_" + purchase_invoice_name + "']")[0].value,
            'posting_date': document.querySelectorAll("input[data-fieldname='posting_date_" + purchase_invoice_name + "']")[0].value,
            'due_date': document.querySelectorAll("input[data-fieldname='due_date_" + purchase_invoice_name + "']")[0].value,
            'bill_no': document.querySelectorAll("input[data-fieldname='bill_no_" + purchase_invoice_name + "']")[0].value,
            'approver': document.querySelectorAll("input[data-fieldname='approver_" + purchase_invoice_name + "']")[0].value,
            'remarks': document.querySelectorAll("textarea[data-fieldname='remarks_" + purchase_invoice_name + "']")[0].value
        };
        
        frappe.call({
            'method': 'microsynth.microsynth.page.invoice_entry.invoice_entry.save_document',
            'args': {
                'doc': doc
            },
            'freeze': true,
            'freeze_message': __("Saving..."),
            'callback': function(response) {
                frappe.show_alert(response.message);
            }
        });
    },
    remove_clearfix_nodes: function() {
        console.log("remove")
        let clearfixes = document.getElementsByClassName("clearfix"); 
        for  (let i = clearfixes.length - 1; i >= 0 ; i--) {
            clearfixes[i].remove();
        }
    }
}

