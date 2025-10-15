/* Custom script extension for Purchase Receipt */
frappe.ui.form.on('Purchase Receipt', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }

        hide_in_words();

        if (!frm.doc.__islocal && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Enter Batches'), function() {
                enter_batches(frm);
            });
        }

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Print Labels'), function() {
                print_labels(frm);
            });
        }

        if (frm.doc.items || frm.doc.items.length > 0) {
            display_material_request_owners(frm);
        }
    },
    before_save(frm) {
        assert_po_and_mr_traces(frm);
    },
    before_submit: function(frm) {
        const item_codes = frm.doc.items.map(row => row.item_code);
        console.log("Checking unbatched items for:", item_codes);

        return frappe.call({
            'method': "microsynth.microsynth.purchasing.check_unbatched_items",
            'args': {
                'item_codes': item_codes
            },
            'freeze': true
        }).then(r => {
            const items_needing_confirmation = r.message || [];

            if (items_needing_confirmation.length > 0) {
                return new Promise((resolve, reject) => {
                    frappe.confirm(
                        __("The following items have never been batched and are not batched now either:<br>{0}Do you want to continue without batching these items permanently?<br>It will <b>not</b> be possible to batch them later.",
                            [`<ul>${items_needing_confirmation.map(i => `<li>${i}</li>`).join('')}</ul>`]
                        ),
                        () => resolve(),  // Continue
                        () => reject(__('Submission cancelled by user'))  // Cancel
                    );
                });
            }
        });
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
    }
});


function enter_batches(frm) {
    // Disable delete rows (hacky trick from allocate_avis dialog on Payment Entry)
    const styles = `
    .grid-delete-row, .grid-remove-rows, .row-actions {
        display: none !important;
    }`;
    const styleSheet = document.createElement("style");
    styleSheet.innerText = styles;
    document.head.appendChild(styleSheet);

    frappe.call({
        'method': "microsynth.microsynth.purchasing.get_batch_items",
        'args': { 'purchase_receipt': frm.doc.name },
        'callback': function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint("No Item requires a Batch.");
                return;
            }

            const d = new frappe.ui.Dialog({
                'title': __('Enter Batch Information'),
                'size': 'extra-large',
                'fields': [
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
                                in_list_view: 1,
                                columns: 3
                            },
                            {
                                fieldname: 'item_name',
                                fieldtype: 'Data',
                                hidden: 1
                            },
                            {
                                fieldname: 'qty',
                                fieldtype: 'Float',
                                label: __('Quantity'),
                                read_only: 1,
                                in_list_view: 1,
                                columns: 1
                            },
                            {
                                fieldname: 'existing_batch',
                                fieldtype: 'Link',
                                label: __('Existing Batch'),
                                options: 'Batch',
                                in_list_view: 1,
                                columns: 2
                            },
                            {
                                fieldname: 'new_batch_id',
                                fieldtype: 'Data',
                                label: __('New Batch ID'),
                                in_list_view: 1,
                                columns: 2
                            },
                            {
                                fieldname: 'new_batch_expiry',
                                fieldtype: 'Date',
                                label: __('Expiry Date'),
                                in_list_view: 1,
                                columns: 2
                            }
                        ]
                    }
                ],
                'primary_action_label': __('Submit'),
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

                        // Colon is not allowed in new_batch_id
                        if (has_new && row.new_batch_id.includes(':')) {
                            frappe.msgprint(__('Colon (:) is not allowed in New Batch ID: "' + row.new_batch_id + '". Please replace by another character.'));
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
                        'method': "microsynth.microsynth.purchasing.create_batches_and_assign",
                        'args': {
                            'purchase_receipt': frm.doc.name,
                            'batch_data': data
                        },
                        'callback': function() {
                            //frappe.msgprint(__('Batches processed successfully.'));
                            frappe.show_alert({message: __('Batches processed successfully.'), indicator: 'green'});
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
                    modals[modals.length - 1].style.width = "1200px";
                }
            }, 300);
        }
    });
}


async function print_labels(frm) {
    let items = frm.doc.items;
    if (!items || items.length === 0) {
        frappe.msgprint(__('No items found.'));
        return;
    }
    const rows = [];

    for (const pr_item of items) {
        if (pr_item.item_code === "P020000") {
            // Skip "Inbound Freight" Item
            continue;
        }
        const item = await frappe.db.get_doc('Item', pr_item.item_code);

        let labels_to_print = pr_item.qty;

        // Handle UOM conversion if needed
        if (pr_item.uom !== pr_item.stock_uom && Array.isArray(item.uoms)) {
            const uom_entry = item.uoms.find(u => u.uom === pr_item.uom);
            if (uom_entry && uom_entry.conversion_factor) {
                labels_to_print = pr_item.qty * uom_entry.conversion_factor;
            }
        }

        // Calculate shelf life date
        const shelf_life_days = item.shelf_life_in_days;
        let shelf_life_date = null;
        if (shelf_life_days) {
            shelf_life_date = frappe.datetime.add_days(frappe.datetime.get_today(), shelf_life_days);
        }

        let internal_code = '';
        if (item.name.length >= 5 && item.name.charAt(item.name.length - 5) === '0') {
            internal_code = item.name.slice(-4);
        }

        rows.push({
            'labels_to_print': Math.round(labels_to_print),
            'item_code': item.item_code,
            'item_name': item.item_name,
            'shelf_life_date': shelf_life_date,
            'material_code': item.material_code,
            'internal_code': internal_code,
            'batch_no': pr_item.batch_no || ''
        });
    }

    const d = new frappe.ui.Dialog({
        'title': __('Print Labels'),
        'size': 'extra-large',
        'fields': [
            {
                'fieldname': 'label_table',
                'fieldtype': 'Table',
                'label': __('Labels to Print'),
                'cannot_add_rows': true,
                'data': rows,
                'get_data': () => rows,
                'fields': [
                    {
                        'fieldname': 'labels_to_print',
                        'fieldtype': 'Int',
                        'label': __('Number of Labels'),
                        'in_list_view': 1,
                        'in_place_edit': 1,
                        'reqd': 1,
                        'columns': 2
                    },
                    {
                        'fieldname': 'item_code',
                        'fieldtype': 'Link',
                        'label': 'Item',
                        'in_list_view': 0,
                        'reqd': 1,
                        'read_only': 1
                    },
                    {
                        'fieldname': 'item_name',
                        'fieldtype': 'Data',
                        'label': __('Item Name'),
                        'read_only': 1,
                        'in_list_view': 1,
                        'columns': 3
                    },
                    {
                        'fieldname': 'shelf_life_date',
                        'fieldtype': 'Date',
                        'label': __('Shelf Life Date'),
                        'in_list_view': 1,
                        'columns': 1
                    },
                    {
                        'fieldname': 'material_code',
                        'fieldtype': 'Data',
                        'label': __('Material Code'),
                        //'read_only': 1,
                        'in_list_view': 1,
                        'columns': 1
                    },
                    {
                        'fieldname': 'internal_code',
                        'fieldtype': 'Data',
                        'label': __('Internal Code'),
                        //'read_only': 1,
                        'in_list_view': 1,
                        'columns': 1
                    },
                    {
                        'fieldname': 'batch_no',
                        'fieldtype': 'Data',
                        'label': __('Batch No'),
                        'read_only': 1,
                        'in_list_view': 1,
                        'columns': 1
                    }
                ]
            }
        ],
        'primary_action_label': __('Print'),
        primary_action(values) {
            //console.log("Labels to print:", values.label_table);
            // call to print
            frappe.call({
                'method': "microsynth.microsynth.labels.print_purchasing_labels",
                'args': {
                    label_table: JSON.stringify(values.label_table)
                },
                'callback': function(r) {
                    frappe.msgprint(__('Labels sent to printer.'));
                }
            });
            //frappe.show_alert("Printing is not yet implemented.");
            d.hide();
        }
    });

    d.show();

    // Make modal wider
    setTimeout(function () {
        const modals = document.getElementsByClassName("modal-dialog");
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = "1200px";
        }
    }, 300);
}


function display_material_request_owners(frm) {
    // Collect info grouped by material_request.owner
    let owner_map = {};

    // Fetch linked Material Requests and their owners
    let material_requests = [];
    frm.doc.items.forEach(item => {
        if (item.material_request) {
            material_requests.push(item.material_request);
        }
    });
    // Remove duplicates
    material_requests = [...new Set(material_requests)];

    if (material_requests.length === 0) return;

    // Fetch Material Requests owners
    frappe.call({
        'method': 'frappe.client.get_list',
        'args': {
            'doctype': 'Material Request',
            'filters': { 'name': ['in', material_requests] },
            'fields': ['name', 'owner'],
        },
        'callback': function(r) {
            if (r.message) {
                let mr_owner_map = {};
                r.message.forEach(mr => {
                    mr_owner_map[mr.name] = mr.owner;
                });
                // Group items by owner
                frm.doc.items.forEach(item => {
                    if (!item.material_request) return;
                    let owner = mr_owner_map[item.material_request];
                    if (!owner) {
                        owner = 'Unknown';
                    }
                    if (!owner_map[owner]) {
                        owner_map[owner] = [];
                    }
                    owner_map[owner].push({
                        'item_name': item.item_name,
                        'item_code': item.item_code,
                        'qty': item.qty
                    });
                });
                // Build comment text
                let comment_html = '<div><b>Material Request Owners and Items:</b><br>';
                for (let owner in owner_map) {
                    comment_html += `<br><b>${owner}</b>:<ul>`;
                    owner_map[owner].forEach(i => {
                        comment_html += `<li>${i.item_code} (${i.item_name}) - Qty: ${i.qty}</li>`;
                    });
                    comment_html += '</ul>';
                }
                comment_html += '</div>';

                // Add dashboard comment/banner
                frm.dashboard.add_comment(comment_html, 'blue', true);
            }
        }
    });
}


function assert_po_and_mr_traces(frm) {
    // Ensure each item line traces to its original Purchase Order and Material Request, grouped by item_code
    const last_po_by_item = {};
    const last_mr_by_item = {};
    const last_mr_item_by_item = {};
    const last_schedule_date_by_item = {};
    let has_changes = false;

    frm.doc.items.forEach(row => {
        const item_code = row.item_code;
        if (!item_code) return;

        // Purchase Order trace
        if (row.purchase_order) {
            last_po_by_item[item_code] = row.purchase_order;
        } else if (last_po_by_item[item_code]) {
            row.purchase_order = last_po_by_item[item_code];
            row.__unsaved = 1;
            has_changes = true;
        }

        // Material Request trace
        if (row.material_request) {
            last_mr_by_item[item_code] = row.material_request;
        } else if (last_mr_by_item[item_code]) {
            row.material_request = last_mr_by_item[item_code];
            row.__unsaved = 1;
            has_changes = true;
        }

        // Material Request Item trace
        if (row.material_request_item) {
            last_mr_item_by_item[item_code] = row.material_request_item;
        } else if (last_mr_item_by_item[item_code]) {
            row.material_request_item = last_mr_item_by_item[item_code];
            row.__unsaved = 1;
            has_changes = true;
        }

        // Required By (Schedule Date) trace
        if (row.schedule_date) {
            last_schedule_date_by_item[item_code] = row.schedule_date;
        } else if (last_schedule_date_by_item[item_code]) {
            row.schedule_date = last_schedule_date_by_item[item_code];
            row.__unsaved = 1;
            has_changes = true;
        }
    });

    if (has_changes) {
        frm.dirty();
    }
}
