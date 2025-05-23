/* Custom script extension for Purchase Receipt */
frappe.ui.form.on('Purchase Receipt', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }
        
        hide_in_words();

        if (!frm.doc.__islocal && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Enter Batches'), function() {

                // Disable delete rows (hacky trick from allocate_avis dialog on Payment Entry)
                const styles = `
                    .grid-delete-row, .grid-remove-rows, .row-actions {
                        display: none !important;
                    }`;
                const styleSheet = document.createElement("style");
                styleSheet.innerText = styles;
                document.head.appendChild(styleSheet);

                frappe.call({
                    method: "microsynth.microsynth.purchasing.get_batch_items",
                    args: { 'purchase_receipt': frm.doc.name },
                    callback: function(r) {
                        if (!r.message || !r.message.length) {
                            frappe.msgprint("No Item requires a Batch.");
                            return;
                        }

                        const d = new frappe.ui.Dialog({
                            title: __('Enter Batch Information'),
                            size: 'extra-large',
                            fields: [
                                {
                                    fieldname: 'batch_table',
                                    fieldtype: 'Table',
                                    label: __('Batch Entries'),
                                    cannot_add_rows: true,
                                    reqd: 1,
                                    data: r.message,
                                    get_data: () => r.message,
                                    fields: [
                                        {
                                            fieldname: 'idx',
                                            fieldtype: 'Data',
                                            label: __('Index'),
                                            read_only: 1,
                                            in_list_view: 0
                                        },
                                        {
                                            fieldname: 'item_code',
                                            fieldtype: 'Link',
                                            label: __('Item'),
                                            options: 'Item',
                                            read_only: 1,
                                            in_list_view: 1
                                        },
                                        {
                                            fieldname: 'item_name',
                                            fieldtype: 'Data',
                                            hidden: 1
                                        },
                                        {
                                            fieldname: 'existing_batch',
                                            fieldtype: 'Link',
                                            label: __('Existing Batch'),
                                            options: 'Batch',
                                            in_list_view: 1
                                        },
                                        {
                                            fieldname: 'new_batch_id',
                                            fieldtype: 'Data',
                                            label: __('New Batch ID'),
                                            in_list_view: 1
                                        },
                                        {
                                            fieldname: 'new_batch_expiry',
                                            fieldtype: 'Date',
                                            label: __('Expiry Date'),
                                            in_list_view: 1
                                        }
                                    ]
                                }
                            ],
                            primary_action_label: __('Submit'),
                            primary_action(values) {
                                const data = values.batch_table;

                                // validate input
                                const invalid = data.find(row => {
                                    const has_existing = !!row.existing_batch;
                                    const has_new = !!row.new_batch_id;
                                    const has_expiry = !!row.new_batch_expiry;
                                
                                    // Must have either existing or new (not both, not neither)
                                    if ((has_existing && has_new) || (!has_existing && !has_new)) {
                                        return true;
                                    }
                                
                                    // If existing batch is selected, new batch fields must be empty
                                    if (has_existing && (has_new || has_expiry)) {
                                        return true;
                                    }
                                
                                    // If new batch ID is given, expiry is optional, so no extra check needed
                                    return false;
                                });
                                
                                if (invalid) {
                                    frappe.msgprint(__('Each row must have either an existing Batch OR a new Batch ID (not both), and Expiry Date is only allowed together with a New Batch ID.'));
                                    return;
                                }

                                // Clean up style on success
                                try { document.head.removeChild(styleSheet); } catch {}

                                frappe.call({
                                    method: "microsynth.microsynth.purchasing.create_batches_and_assign",
                                    args: {
                                        'purchase_receipt': frm.doc.name,
                                        'batch_data': data
                                    },
                                    callback: function() {
                                        frappe.msgprint(__('Batches processed successfully.'));
                                        frm.reload_doc();
                                        d.hide();
                                    }
                                });
                            },
                            secondary_action: function() {
                                try { document.head.removeChild(styleSheet); } catch {}
                            }
                        });

                        d.show();

                        // forces a readable width (hacky trick from allocate_avis dialog on Payment Entry)
                        setTimeout(function () {
                            const modals = document.getElementsByClassName("modal-dialog");
                            if (modals.length > 0) {
                                modals[modals.length - 1].style.width = "1000px";
                            }
                        }, 300);
                    }
                });
            });
        }
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }            
    }
});
