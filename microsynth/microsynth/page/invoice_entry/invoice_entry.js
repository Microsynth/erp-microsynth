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

// iframe interaction handler
window.onmessage = function(e) {
    if ((typeof e.data === "string") && ((e.data).startsWith("iframe_saved"))) {
        let parts = e.data.split(" ");
        if (parts.length > 1) {
            // close form view
            frappe.invoice_entry.open_edit_form(parts[1], close=true);
            // only update selected part
            frappe.invoice_entry.fetch_purchase_invoice(parts[1]);
        } else {
            // no document reference provided - need to reload all
            location.reload();
        }
    }
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
            html = "<h1>Nothing to do 😎</h1>"  // Add button "Load invoices" that triggers batch_invoice_processing.process_files
            //html += '<button class="btn btn-sm btn-primary" id="btn_import" onclick="import_invoices()">Import Invoices now</button>'
        }
        // insert content
        document.getElementById("pi_drafts_view").innerHTML = html;

        for (let i = 0; i < purchase_invoice_drafts.length; i++) {
            frappe.invoice_entry.create_fields(purchase_invoice_drafts[i]);
            frappe.invoice_entry.attach_save_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_assign_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_edit_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_close_handler(purchase_invoice_drafts[i].name);
            frappe.invoice_entry.attach_delete_handler(purchase_invoice_drafts[i].name);
            // Attach handler for button to select a PO independent of the supplier
            frappe.invoice_entry.attach_select_po_button_handler(purchase_invoice_drafts[i].name);

            // Attach PO selection handler for each Purchase Order of this supplier
            for (let po of purchase_invoice_drafts[i].purchase_orders) {
                frappe.invoice_entry.attach_po_selection_handler(purchase_invoice_drafts[i].name, po.name);
            }
        }

        // clean help boxes to save some space below each input box
        let help_boxes = document.getElementsByClassName("help-box");
        for (let i = 0; i < help_boxes.length; i++) {
            help_boxes[0].remove();
        }
    },
    create_fields: function(purchase_invoice) {
        frappe.invoice_entry.create_field(purchase_invoice, 'Link', 'supplier', 'Supplier', 'Supplier');
        frappe.invoice_entry.create_field(purchase_invoice, 'Date', 'bill_date', 'Supplier Invoice Date', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Date', 'posting_date', 'Posting Date', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Date', 'due_date', 'Due Date', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Data', 'bill_no', 'Supplier Invoice No', '');
        frappe.invoice_entry.create_field(purchase_invoice, 'Link', 'approver', 'Approver', 'User');
        frappe.invoice_entry.create_field(purchase_invoice, 'Data', 'remarks', 'Remarks', '');
        if (purchase_invoice.allow_edit_net_amount) {
            frappe.invoice_entry.create_field(purchase_invoice, 'Currency', 'net_total', 'Total', '');
        }
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
    fetch_purchase_invoice: function(purchase_invoice) {
        // fetch document
        frappe.call({
            'method': 'microsynth.microsynth.page.invoice_entry.invoice_entry.get_purchase_invoice_drafts',
            'args': {
                'purchase_invoice': purchase_invoice
            },
            'callback': function(r) {
                var purchase_invoice_values = r.message[0];
                frappe.invoice_entry.update_display_fields(purchase_invoice_values);
            }
        });
    },
    update_display_fields: function(purchase_invoice_values) {
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'supplier', purchase_invoice_values.supplier);
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'supplier_name', purchase_invoice_values.supplier_name);
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'due_date', frappe.datetime.obj_to_user(purchase_invoice_values.due_date));
        // check if due date is in the past
        if (purchase_invoice_values.due_date <= frappe.datetime.get_today()) {
            document.getElementById("due_date_" + purchase_invoice_values.name).parentNode.parentNode.classList.add("highlight-row");
        } else {
            document.getElementById("due_date_" + purchase_invoice_values.name).parentNode.parentNode.classList.remove("highlight-row");
        }
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'bill_date', frappe.datetime.obj_to_user(purchase_invoice_values.bill_date));
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'posting_date', frappe.datetime.obj_to_user(purchase_invoice_values.posting_date));
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'bill_no', purchase_invoice_values.bill_no);
        if (purchase_invoice_values.allow_edit_net_amount === 1) {
            frappe.invoice_entry.set_field(purchase_invoice_values.name,
                'net_total', format_currency(purchase_invoice_values.net_total));
        } else {
            frappe.invoice_entry.set_div(purchase_invoice_values.name,
                'net_total', purchase_invoice_values.currency + " " + format_currency(purchase_invoice_values.net_total));
        }
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'taxes', purchase_invoice_values.currency + " " + format_currency(purchase_invoice_values.total_taxes_and_charges));
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'grand_total', purchase_invoice_values.currency + " " + format_currency(purchase_invoice_values.grand_total));
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'tax_template', purchase_invoice_values.taxes_and_charges);
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'expense_account', purchase_invoice_values.expense_account + " / " + purchase_invoice_values.cost_center);
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'iban', purchase_invoice_values.iban);
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'esr_participation_number', purchase_invoice_values.esr_participation_number);
        frappe.invoice_entry.set_div(purchase_invoice_values.name,
            'payment_method', purchase_invoice_values.default_payment_method);
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'approver', purchase_invoice_values.approver);
        frappe.invoice_entry.set_field(purchase_invoice_values.name,
            'remarks', purchase_invoice_values.remarks);
    },
    set_field: function(purchase_invoice, field_name, value) {
        let field = document.querySelector("input[data-fieldname='" + field_name + "_" + purchase_invoice + "']");
        if (field) {
            field.value = value;
        } else {
            console.warn(`Field '${field_name}' for Purchase Invoice '${purchase_invoice}' not found.`);
        }
    },
    set_div: function(purchase_invoice, field_name, value) {
        let div = document.getElementById(field_name + "_" + purchase_invoice);
        if (div) {
            try {
                div.innerHTML = value;
            } catch (error) {
                console.error(`Error setting value for div '${field_name}' on Purchase Invoice '${purchase_invoice}':`, error);
            }
        } else {
            console.warn(`Div '${field_name}' for Purchase Invoice '${purchase_invoice}' not found.`);
        }
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
    attach_delete_handler: function(purchase_invoice_name) {
        let btn_delete = document.getElementById("btn_delete_" + purchase_invoice_name);
        btn_delete.onclick = frappe.invoice_entry.delete_document.bind(this, purchase_invoice_name);
    },
    attach_po_selection_handler: function(purchase_invoice_name, purchase_order_name) {
        let po_button = document.querySelector(`button[data-po-name="${purchase_order_name}"][data-pi-name="${purchase_invoice_name}"]`);
        if (po_button) {
            po_button.addEventListener('click', function() {
                let bill_no = document.querySelector(`input[data-fieldname='bill_no_${purchase_invoice_name}']`).value || null;
                frappe.call({
                    method: 'microsynth.microsynth.page.invoice_entry.invoice_entry.update_pi_according_to_po',
                    args: {
                        purchase_order_name: purchase_order_name,
                        purchase_invoice_name: purchase_invoice_name,
                        bill_no: bill_no // Pass bill_no to the backend
                    },
                    callback: function(response) {
                        if (response.message.success) {
                            // Fetch updated Purchase Invoice details and refresh the UI
                            frappe.invoice_entry.fetch_purchase_invoice(purchase_invoice_name);
                        } else {
                            frappe.show_alert(response.message.message);
                        }
                    }
                });
            });
        } else {
            console.error(`Button for PO ${purchase_order_name} and PI ${purchase_invoice_name} not found.`);
        }
    },
    attach_select_po_button_handler: function(purchase_invoice_name) {
        let btn = document.getElementById("btn_select_po_" + purchase_invoice_name);
        if (!btn) return;
        // Get company from the Purchase Invoice row
        let company = document.querySelector(`#row_${purchase_invoice_name} .text-muted`).innerText;

        btn.addEventListener("click", function () {
            frappe.prompt([
                {
                    fieldtype: 'Link',
                    label: 'Purchase Order',
                    fieldname: 'purchase_order',
                    options: 'Purchase Order',
                    reqd: 1,
                    get_query: function () {
                        return {
                            'filters': {
                                'docstatus': 1,
                                'status': ['not in', ['Completed', 'Closed']],
                                'company': company
                            }
                        };
                    }
                }
            ],
            function (values) {
                let purchase_order_name = values.purchase_order;
                let bill_no = document.querySelector(`input[data-fieldname='bill_no_${purchase_invoice_name}']`).value || null;

                frappe.call({
                    'method': 'microsynth.microsynth.page.invoice_entry.invoice_entry.update_pi_according_to_po',
                    'args': {
                        'purchase_order_name': purchase_order_name,
                        'purchase_invoice_name': purchase_invoice_name,
                        'bill_no': bill_no
                    },
                    callback: function (response) {
                        if (response.message.success) {
                            frappe.invoice_entry.fetch_purchase_invoice(purchase_invoice_name);
                        } else {
                            frappe.show_alert(response.message.message);
                        }
                    }
                });
            },
            __('Select Purchase Order'),
            __('Confirm')
            );
        });
    },
    save_document: function(purchase_invoice_name, edit_mode=false) {
        let net_total_inputs = document.querySelectorAll("input[data-fieldname='net_total_" + purchase_invoice_name + "']");
        let net_total = null;
        if ((net_total_inputs) && (net_total_inputs.length > 0)) {
            net_total = net_total_inputs[0].value;
        }
        let doc = {
            'name': purchase_invoice_name,
            'supplier': document.querySelectorAll("input[data-fieldname='supplier_" + purchase_invoice_name + "']")[0].value,
            'bill_date': document.querySelectorAll("input[data-fieldname='bill_date_" + purchase_invoice_name + "']")[0].value,
            'posting_date': document.querySelectorAll("input[data-fieldname='posting_date_" + purchase_invoice_name + "']")[0].value,
            'due_date': document.querySelectorAll("input[data-fieldname='due_date_" + purchase_invoice_name + "']")[0].value,
            'bill_no': document.querySelectorAll("input[data-fieldname='bill_no_" + purchase_invoice_name + "']")[0].value,
            'approver': document.querySelectorAll("input[data-fieldname='approver_" + purchase_invoice_name + "']")[0].value,
            'remarks': document.querySelectorAll("input[data-fieldname='remarks_" + purchase_invoice_name + "']")[0].value,
            'net_total': net_total
        };
        frappe.call({
            'method': 'microsynth.microsynth.page.invoice_entry.invoice_entry.save_document',
            'args': {
                'doc': doc
            },
            'freeze': true,
            'freeze_message': __("Saving..."),
            'callback': function(response) {
                if (response.message.success) {
                    if (edit_mode===true) {
                        frappe.invoice_entry.open_edit_form(purchase_invoice_name);
                    } else {
                        //location.reload();
                        frappe.invoice_entry.fetch_purchase_invoice(purchase_invoice_name);
                    }
                } else {
                    frappe.show_alert(response.message.message);
                }
            }
        });
    },
    assign_document: function(purchase_invoice_name) {
        this.save_document(purchase_invoice_name);
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
        // save without reload
        this.save_document(purchase_invoice_name, edit_mode=true);
    },
    open_edit_form: function(purchase_invoice_name, close=false) {
        // toggle quick entry/form
        let quick_entry = document.getElementById("quick_entry_" + purchase_invoice_name);
        let full_form = document.getElementById("full_form_" + purchase_invoice_name);
        let form_frame = document.getElementById("form_frame_" + purchase_invoice_name);

        if (close) {
            // close edit iframe
            quick_entry.style.display = "Block";
            full_form.style.display = "None";
            // clean form
            form_frame.innerHTML = "";
        } else {

            quick_entry.style.display = "None";
            full_form.style.display = "Block";
            // load full form
            form_frame.innerHTML = "<iframe id='iframe_" + purchase_invoice_name + "' class='pdf' style='width: 100%; border: 0px; margin-top: 5px;' src='/desk#Form/Purchase Invoice/" + purchase_invoice_name + "'></iframe>";
        }
    },
    close_document: function(purchase_invoice_name) {
        let iframe = document.getElementById("iframe_" + purchase_invoice_name);
        if (iframe) {
            iframe.contentWindow.postMessage("close_document", {});
        }
    },
    delete_document: function(purchase_invoice_name) {
        // let the user confirm the deletion
        frappe.confirm('Are you sure you want to <b>delete</b> ' + purchase_invoice_name + '? This cannot be undone.',
        () => {
            frappe.call({
                'method': 'microsynth.microsynth.page.invoice_entry.invoice_entry.delete_document',
                'args': {
                    'purchase_invoice_name': purchase_invoice_name
                },
                'freeze': true,
                'freeze_message': __("Deleting ..."),
                'callback': function(response) {
                    frappe.show_alert(response.message);
                    setTimeout(function () {location.reload();}, 100);
                }
            })
        }, () => {
            frappe.show_alert('Did <b>not</b> delete' + purchase_invoice_name + '.');
        });
    },
    remove_clearfix_nodes: function() {
        let clearfixes = document.getElementsByClassName("clearfix");
        for  (let i = clearfixes.length - 1; i >= 0 ; i--) {
            clearfixes[i].remove();
        }
    }
}


function import_invoices() {
    console.log("Going to import ...");
        frappe.call({
            'method': 'microsynth.microsynth.batch_invoice_processing.process_files',
            'freeze': true,
            'freeze_message': __("Loading ..."),
            'callback': function(response) {
                location.reload();
            }
        });
}

function format_currency(n) {
    return (n || 0).toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "'");
}
