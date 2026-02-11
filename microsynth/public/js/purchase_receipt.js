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

        // allow force cancel
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0) && (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User'))) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            });
        }

        if (!frm.doc.__islocal) {
            frm.add_custom_button("Related Documents", function () {
                frappe.set_route("query-report", "Purchase Document Overview", {
                    "document_id": frm.doc.name
                });
            }, __("View"));
        }

        if (frm.doc.items && frm.doc.items.length > 0) {
            display_mr_owners_and_storage_locations(frm);
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
        'method': "microsynth.microsynth.purchasing.get_set_batch_items",
        'args': { 'purchase_receipt': frm.doc.name },
        'callback': function(r) {
            // r.message is [batch_items, warnings]
            const batch_items = r.message && r.message[0] ? r.message[0] : [];
            const warnings = r.message && r.message[1] ? r.message[1] : [];
            if (!batch_items.length) {
                frappe.msgprint("No Item requires a Batch and it is not possible anymore to activate batching for these Items.");
                return;
            }
            // Show warnings using frappe.show_alert()
            if (warnings && warnings.length) {
                frappe.show_alert({
                    message: __(warnings.join("<br>")),
                    indicator: 'orange'
                });
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
                        data: batch_items,
                        get_data: () => batch_items,
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
                                columns: 2,
                                // Restrict the batch link options to the same Item
                                get_query: function(row) {
                                    return {
                                        filters: {
                                            'item': row.item_code || ''
                                        }
                                    };
                                }
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

                    // Check if existing batches belong to correct Item
                    const existing_batches = data
                        .filter(row => row.existing_batch)
                        .map(row => row.existing_batch);

                    if (existing_batches.length > 0) {
                        frappe.db.get_list('Batch', {
                            fields: ['name', 'item'],
                            filters: [['name', 'in', existing_batches]]
                        }).then(batch_list => {
                            const batch_map = {};
                            (batch_list || []).forEach(b => batch_map[b.name] = b.item);

                            const wrong = data.filter(row =>
                                row.existing_batch && batch_map[row.existing_batch] !== row.item_code
                            );

                            if (wrong.length > 0) {
                                const bad = wrong.map(r => `${r.existing_batch} (Item: ${batch_map[r.existing_batch]}, Expected: ${r.item_code})`).join('<br>');
                                frappe.msgprint({
                                    title: __('Invalid Batch Assignments'),
                                    message: __('The following existing batches belong to different items:<br>') + bad,
                                    indicator: 'red'
                                });
                                return;
                            }
                            // Proceed only if all good
                            finalize_batches();
                        });
                    } else {
                        finalize_batches();
                    }

                    function finalize_batches() {
                        // Clean up style on success
                        try { document.head.removeChild(styleSheet); } catch {}

                        frappe.call({
                            'method': "microsynth.microsynth.purchasing.create_batches_and_assign",
                            'args': {
                                'purchase_receipt': frm.doc.name,
                                'batch_data': data
                            },
                            'callback': function() {
                                frappe.show_alert({message: __('Batches processed successfully.'), indicator: 'green'});
                                frm.reload_doc();
                                d.hide();
                            }
                        });
                    }
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
            'batch_no': pr_item.batch_no || '',
            'serial_no': pr_item.serial_no || ''
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
            frappe.call({
                'method': "microsynth.microsynth.labels.print_purchasing_labels",
                'args': {
                    label_table: JSON.stringify(values.label_table)
                },
                'callback': function(r) {
                    frappe.msgprint(__('Labels sent to printer.'));
                }
            });
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


function display_mr_owners_and_storage_locations(frm) {
    // Collect info grouped by material_request.owner
    let owner_map = {};
    let item_codes = [];

    // Fetch linked Material Requests and their owners
    let material_requests = [];
    frm.doc.items.forEach(item => {
        if (item.material_request) {
            material_requests.push(item.material_request);
        }
        if (item.item_code) {
            item_codes.push(item.item_code);
        }
    });
    // Remove duplicates
    material_requests = [...new Set(material_requests)];
    item_codes = [...new Set(item_codes)];

    if (material_requests.length === 0) return;

    // Fetch Material Requests owners
    frappe.call({
        'method': 'frappe.client.get_list',
        'args': {
            'doctype': 'Material Request',
            'filters': { 'name': ['in', material_requests] },
            'fields': ['name', 'requested_by', 'owner'],
        },
        'callback': function(r) {
            if (r.message) {
                let mr_owner_map = {};
                r.message.forEach(mr => {
                    mr_owner_map[mr.name] = mr.requested_by || mr.owner || 'Unknown';
                });
                // Fetch all Item docs with storage_locations child table
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Item',
                        filters: { name: ['in', item_codes] },
                        fields: ['name', 'item_name'],
                        limit_page_length: 1000
                    },
                    callback: function(itemres) {
                        let item_map = {};
                        let item_promises = [];
                        (itemres.message || []).forEach(item => {
                            // For each item, fetch full doc to get storage_locations child table
                            item_promises.push(
                                frappe.call({
                                    method: 'frappe.client.get',
                                    args: {
                                        doctype: 'Item',
                                        name: item.name
                                    }
                                }).then(r => {
                                    item_map[item.name] = r.message;
                                })
                            );
                        });
                        Promise.all(item_promises).then(() => {
                            // For all unique locations, fetch their full path (as in item.js)
                            let all_locations = new Set();
                            Object.values(item_map).forEach(itemdoc => {
                                (itemdoc.storage_locations || []).forEach(row => all_locations.add(row.location));
                            });
                            all_locations = Array.from(all_locations);
                            let location_path_promises = all_locations.map(loc =>
                                frappe.call({
                                    method: "microsynth.microsynth.purchasing.get_location_path_string",
                                    args: { location_name: loc },
                                }).then(r => [loc, r.message])
                            );
                            Promise.all(location_path_promises).then(location_path_pairs => {
                                let location_path_map = {};
                                location_path_pairs.forEach(([loc, path]) => {
                                    location_path_map[loc] = path;
                                });
                                // Reworked: show a table with columns Requester | Supplier Item Code | Item Code | Item Name | Qty | UOM | Storage Locations
                                let comment_html = `<div style="overflow-x:auto;"><table class="table table-bordered" style="margin-bottom: 8px; min-width: 900px;">
                                    <thead>
                                        <tr>
                                            <th>Requested by</th>
                                            <th>Supplier Item Code</th>
                                            <th>Item Name</th>
                                            <th>Qty</th>
                                            <th>UOM</th>
                                            <th>Batch No</th>
                                            <th>Storage Location(s)</th>
                                        </tr>
                                    </thead>
                                    <tbody>`;
                                frm.doc.items.forEach(i => {
                                    if (!i.material_request) return;
                                    let owner = mr_owner_map[i.material_request];
                                    if (!owner) {
                                        owner = 'Unknown';
                                    }
                                    // Find the item row in frm.doc.items to get more info
                                    let item_row = (frm.doc.items || []).find(row => row.item_code === i.item_code && row.item_name === i.item_name && row.qty === i.qty);
                                    let supplier_item_code = '';
                                    let uom = '';
                                    let batch_no = '';
                                    if (item_row) {
                                        supplier_item_code = item_row.supplier_part_no || '';
                                        uom = item_row.uom || '';
                                        batch_no = item_row.batch_no || '';
                                    }
                                    let itemdoc = item_map[i.item_code];
                                    let locs = (itemdoc && itemdoc.storage_locations) ? itemdoc.storage_locations.map(row => row.location) : [];
                                    let location_paths = locs.map(loc => location_path_map[loc]).filter(Boolean);
                                    comment_html += `<tr>`;
                                    comment_html += `<td>${owner}</td>`;
                                    comment_html += `<td>${frappe.utils.escape_html(supplier_item_code)}</td>`;
                                    comment_html += `<td>${frappe.utils.escape_html(i.item_name)}</td>`;
                                    comment_html += `<td>${i.qty}</td>`;
                                    comment_html += `<td>${frappe.utils.escape_html(uom)}</td>`;
                                    comment_html += `<td>${frappe.utils.escape_html(batch_no)}</td>`;
                                    if (location_paths && location_paths.length) {
                                        comment_html += `<td><span class='text-muted'>${location_paths.map(p => frappe.utils.escape_html(p)).join('; ')}</span></td>`;
                                    } else {
                                        comment_html += `<td><b>No Storage Location set on this Item</b></td>`;
                                    }
                                    comment_html += `</tr>`;
                                });
                                comment_html += `</tbody></table></div>`;
                                // Add dashboard comment/banner
                                frm.dashboard.add_comment(comment_html, 'blue', true);
                            });
                        });
                    }
                });
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
