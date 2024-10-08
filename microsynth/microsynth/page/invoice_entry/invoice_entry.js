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
        if (purchase_invoice_drafts.length == 0) {
            html = "<h1>Nothing to do 😎</h1>"
        }
        // insert content
        document.getElementById("pi_drafts_view").innerHTML = html;
        
        for (let i = 0; i < purchase_invoice_drafts.length; i++) {
            frappe.invoice_entry.create_fields(purchase_invoice_drafts[i]);
            frappe.invoice_entry.attach_save_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_assign_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_edit_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_close_handler(purchase_invoice_drafts[i].name);
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
    attach_edit_handler: function(purchase_invoice_name) {
        let btn_edit = document.getElementById("btn_edit_" + purchase_invoice_name);
        btn_edit.onclick = frappe.invoice_entry.edit_document.bind(this, purchase_invoice_name);
    },
    attach_assign_handler: function(purchase_invoice_name) {
        let btn_assign = document.getElementById("btn_assign_" + purchase_invoice_name);
        btn_assign.onclick = frappe.invoice_entry.assign_document.bind(this, purchase_invoice_name);
    },
    attach_close_handler: function(purchase_invoice_name) {
        let btn_close = document.getElementById("btn_close_" + purchase_invoice_name);
        btn_close.onclick = frappe.invoice_entry.close_document.bind(this, purchase_invoice_name);
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
    assign_document: function(purchase_invoice_name) {        
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.create_approval_request',
            'args': {
                'assign_to': document.querySelectorAll("input[data-fieldname='approver_" + purchase_invoice_name + "']")[0].value,
                'dt': 'Purchase Invoice',
                'dn': purchase_invoice_name
            },
            'freeze': true,
            'freeze_message': __("Assigning ..."),
            'callback': function(response) {
                if (response.message) {
                    frappe.show_alert("Sucessfully assigned");
                    document.getElementById("row_" + purchase_invoice_name).style.display = "None";
                } else {
                    frappe.show_alert("Failed assigning");
                }
            }
        });
    },
    edit_document: function(purchase_invoice_name) {
        // toggle quick entry/form
        let quick_entry = document.getElementById("quick_entry_" + purchase_invoice_name);
        quick_entry.style.display = "None";
        let full_form = document.getElementById("full_form_" + purchase_invoice_name);
        full_form.style.display = "Block";
        // load full form
        let form_frame = document.getElementById("form_frame_" + purchase_invoice_name);
        form_frame.innerHTML = "<iframe class='pdf' style='width: 100%; border: 0px; margin-top: 5px;' src='/desk#Form/Purchase Invoice/" + purchase_invoice_name + "'></iframe>";
    },
    close_document: function(purchase_invoice_name) {
        /*
        // toggle quick entry/form
        let quick_entry = document.getElementById("quick_entry_" + purchase_invoice_name);
        quick_entry.style.display = "Block";
        let full_form = document.getElementById("full_form_" + purchase_invoice_name);
        full_form.style.display = "None";
        // unload form
        let form_frame = document.getElementById("form_frame_" + purchase_invoice_name);
        form_frame.innerHTML = "";
        */
        location.reload();
    },
    remove_clearfix_nodes: function() {
        console.log("remove")
        let clearfixes = document.getElementsByClassName("clearfix"); 
        for  (let i = clearfixes.length - 1; i >= 0 ; i--) {
            clearfixes[i].remove();
        }
    }
}

