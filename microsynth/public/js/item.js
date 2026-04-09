/* Custom script extension for Item */

frappe.ui.form.on('Item', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            cur_frm.set_value('is_stock_item', false);
            cur_frm.set_value('include_item_in_manufacturing', false);
        }
        if (frm.doc.__islocal && frm.doc.item_group && frm.doc.item_group == 'Purchasing') {
            cur_frm.set_value('is_stock_item', true);
        }

        // Only show button for Item Group "Purchasing"
        if (frm.doc.item_group === "Purchasing") {
            frm.add_custom_button(__("Add Location"), function () {
                show_add_location_dialog(frm);
            });

            if (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User')) {
                frm.add_custom_button(__("Add/Edit Price"), function () {
                    add_edit_purchasing_price(frm);
                });
            }
        }

        // Show "Correct Stock" button only for non-disabled stock items and users with Stock User role
        if (
            !frm.doc.__islocal &&
            frm.doc.disabled === 0 &&
            frm.doc.is_stock_item &&
            frappe.user.has_role("Stock User")
        ) {
            frm.add_custom_button("Correct Stock", () => {
                open_correct_stock_dialog(frm);
            });
        }

        if (frm.doc.storage_locations.length > 0) {
            // Remove previous dashboard comments
            frm.dashboard.clear_comment();

            // Collect all location paths
            const storage_locations = frm.doc.storage_locations || [];

            if (!storage_locations.length) return;

            const location_promises = storage_locations.map(row => {
                return frappe.call({
                    method: "microsynth.microsynth.purchasing.get_location_path_string",
                    args: { location_name: row.location },
                });
            });

            // Wait for all calls to finish
            Promise.all(location_promises).then(results => {
                const paths = results
                    .map(r => r.message)
                    .filter(p => p); // remove empty

                if (!paths.length) return;

                const text = `<b>Storage Location${paths.length > 1 ? "s" : ""}:</b><br>${paths.join("<br>")}`;

                // Add permanent green dashboard comment
                frm.dashboard.add_comment(text, 'green', true);
            });
        }

        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Link with other Item"), function () {
                frappe.prompt(
                    [
                        {
                            label: "Item to link",
                            fieldname: "item_to_link",
                            fieldtype: "Link",
                            options: "Item",
                            reqd: 1
                        }
                    ],
                    function (data) {
                        frappe.call({
                            'method': "microsynth.microsynth.purchasing.link_items_symmetrically",
                            'args': {
                                'item_a': frm.doc.name,
                                'item_b': data.item_to_link
                            },
                            'callback': function (r) {
                                frm.reload_doc();
                                frappe.msgprint(__("Items linked successfully."));
                            }
                        });
                    },
                    __("Select Item to Link"),
                    __("Link")
                );
            });
        }
    },
    validate(frm) {
        // Only when trying to disable an existing item
        if (!frm.doc.__islocal && frm.doc.disabled && !frm.doc.__checked_open_docs) {
            (async function () {
                const item_code = frm.doc.name;

                const getOpenDocsHtml = (docs) =>
                    docs.map(doc =>
                        `<li>${doc.doctype} <a href="${doc.url}" target="_blank">${doc.name}</a></li>`
                    ).join("");

                const result = await frappe.call({
                    'method': "microsynth.microsynth.utils.get_open_documents_for_item",
                    'args': { item_code },
                    'freeze': true,
                    'freeze_message': "Checking open documents ..."
                });
                const open_docs_by_type = result.message || {};
                const open_docs = Object.entries(open_docs_by_type)
                    .flatMap(([doctype, docs]) =>
                        docs.map(doc => ({ ...doc, doctype }))
                    );
                if (open_docs.length > 0) {
                    const openDocsHtml = getOpenDocsHtml(open_docs);
                    const dialog = new frappe.ui.Dialog({
                        'title': __("Open documents with Item") + " " + item_code,
                        'indicator': "orange",
                        'fields': [{
                            'fieldtype': "HTML",
                            'fieldname': "message",
                            'options': `
                                <div>
                                    ${__("This Item is used in open sales documents and should <b>not</b> be <b>disabled</b>.")}
                                    <br>
                                    ${__("Please set the Item to Sales Status <b>Discontinued</b> instead.")}
                                    <br><br>
                                    ${__("Please check to complete or close the open sales documents:")}
                                    <br><br>
                                    <ul>${openDocsHtml}</ul>
                                </div>
                            `
                        }],
                        'primary_action_label': __("Set to Discontinued"),
                        'secondary_action_label': __("Cancel")
                    });
                    dialog.set_primary_action(__("Set to Discontinued"), async function () {
                        frm.set_value("sales_status", "Discontinued");
                        frm.set_value("disabled", 0);
                        frm.doc.__checked_open_docs = true;
                        await frm.save();
                        dialog.hide();
                    });
                    dialog.set_secondary_action(() => dialog.hide());
                    dialog.show();
                    frappe.validated = false;
                    return;
                }
                // No open docs → allow disabling
                frm.doc.__checked_open_docs = true;
                frm.save();
            })();
            frappe.validated = false;
        }
        // Prevent pack_uom == stock_uom if pack_size != 1
        if (frm.doc.pack_uom && frm.doc.stock_uom && frm.doc.pack_uom === frm.doc.stock_uom && frm.doc.pack_size != 1) {
            frappe.msgprint(__("Pack UOM cannot be the same as Stock UOM if Pack Size is not 1."));
            frappe.validated = false;
        }
        // Prevent multiple lines for the same supplier in Item Supplier table
        if (frm.doc.supplier_items) {
            const seenSuppliers = new Set();
            for (const row of frm.doc.supplier_items) {
                if (seenSuppliers.has(row.supplier)) {
                    frappe.msgprint(__("Supplier {0} is listed multiple times in the Supplier Items table. Please keep only one entry per supplier.", [row.supplier]));
                    frappe.validated = false;
                    break;
                }
                seenSuppliers.add(row.supplier);
            }
        }
    },
    has_batch_no(frm) {
        if (!frm.doc.has_batch_no) {
            frm.set_value('batch_type', '');
        }
    }
});


function add_edit_purchasing_price(frm) {
    // Fetches default_price_list from Supplier from supplier_items table (expected exactly one with Item Supplier.substitute_status empty or Verified)
    // Checks if there are already any Item Prices for this Item on the fetched Price List with any minimum qty (show them)
    // Asks to add or update an Item Price (default min_qty = 1)
    // Calls a backend function that does the operation with ignore_permission=True
    if (!frm.doc.name) {
        frappe.msgprint(__("Please save the Item first."));
        return;
    }
    frappe.call({
        'method': "microsynth.microsynth.purchasing.get_purchasing_price_context",
        'args': {
            'item_code': frm.doc.name
        },
        'freeze': true,
        'callback': function (r) {
            const price_context = r.message;
            if (!price_context || !price_context.price_list) {
                frappe.msgprint(
                    __("Could not uniquely determine a Supplier Price List for this Item. Please check the Supplier Items table and the Price List of the linked Supplier(s).")
                );
                return;
            }
            let existing_html = `
                <div class="form-group">
                    <label class="control-label">
                        ${__("Existing Prices")}
                    </label>
            `;
            if (price_context.existing_prices.length) {
                // Right align all headers and data in table
                existing_html += `
                    <table class="table table-sm" style="margin-top: 4px;">
                        <thead>
                            <tr>
                                <th style="padding-left: 0; text-align: right;">
                                    ${__("Min Qty")}
                                </th>
                                <th style="padding-left: 0; text-align: right;">
                                    ${__("Unit")}
                                </th>
                                <th style="padding-left: 0; text-align: right;">
                                    ${__("Rate")}
                                </th>
                                <th style="padding-left: 0; text-align: right;">
                                    ${__("Currency")}
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                price_context.existing_prices.forEach(row => {
                    existing_html += `
                        <tr>
                            <td style="padding-left: 0; text-align: right;">
                                ${frappe.format(row.min_qty, { fieldtype: "Float" })}
                            </td>
                            <td style="padding-left: 0; text-align: right;">
                                ${row.uom || ""}
                            </td>
                            <td style="padding-left: 0; text-align: right;">
                                <strong>
                                    ${frappe.format(row.price_list_rate, {
                                        fieldtype: "Float",
                                        precision: 2,
                                    })}
                                </strong>
                            </td>
                            <td style="padding-left: 0; text-align: right;">
                                ${price_context.currency}
                            </td>
                        </tr>
                    `;
                });
                existing_html += `
                        </tbody>
                    </table>
                `;
            } else {
                existing_html += `
                    <div class="text-muted small" style="margin-top: 4px;">
                        ${__(
                            "No existing Item Prices for Supplier <b>{0}</b> in Price List <b>{1}</b>.",
                            [
                                price_context.supplier,
                                price_context.price_list
                            ]
                        )}
                    </div>
                `;
            }
            existing_html += `</div>`;

            // Compute conversion info: If purchase_uom and stock_uom differ, display conversion text
            let conversion_info = '';
            if (frm.doc.purchase_uom && frm.doc.stock_uom && frm.doc.purchase_uom !== frm.doc.stock_uom) {
                let cf = 1;
                for (const uom of frm.doc.uoms || []) {
                    if (uom.uom === frm.doc.purchase_uom) {
                        cf = uom.conversion_factor;
                        break;
                    }
                }
                let stock_uom = frm.doc.stock_uom || "";
                let plural = stock_uom.toLowerCase().endsWith("s") || cf <= 1 ? "" : "s";
                conversion_info = __(
                    '1 {0} = {1} {2}{3}',
                    [
                        frm.doc.purchase_uom,
                        cf,
                        stock_uom,
                        plural
                    ]
                );
            }

            const dialog = new frappe.ui.Dialog({
                'title': __("Add / Edit Purchasing Price"),
                'fields': [
                    {
                        fieldname: "price_list",
                        fieldtype: "Data",
                        label: __("Price List"),
                        read_only: 1,
                        default: price_context.price_list
                    },
                    {
                        fieldtype: "Column Break"
                    },
                    {
                        fieldname: "conversion_info",
                        fieldtype: "Data",
                        label: __("Conversion Info"),
                        read_only: 1,
                        default: conversion_info  // If purchase_uom and purchase_uom != stock_uom, show conversion from purchase_uom to stock_uom: e.g. "1 box = 10 pieces", else ""
                    },
                    {
                        fieldtype: "Section Break"
                    },
                    {
                        fieldname: "existing_prices",
                        fieldtype: "HTML",
                        label: __("Existing Prices"),
                        options: existing_html
                    },
                    {
                        fieldtype: "Section Break"
                    },
                    {
                        fieldname: "min_qty",
                        fieldtype: "Int",
                        label: __("Minimum Quantity"),
                        reqd: 1,
                        default: 1
                    },
                    {
                        fieldname: "price_list_rate",
                        fieldtype: "Currency",
                        label: __("Price per Unit"),
                        reqd: 1
                    },
                    {
                        fieldtype: "Column Break"
                    },
                    {
                        fieldname: "uom",
                        fieldtype: "Data",
                        label: __("Unit"),
                        reqd: 1,
                        default: frm.doc.purchase_uom || frm.doc.stock_uom
                    },
                    {
                        fieldname: "currency",
                        fieldtype: "Data",
                        label: __("Currency"),
                        read_only: 1,
                        default: price_context.currency
                    }

                ],
                'primary_action_label': __("Save"),
                primary_action(values) {
                    frappe.call({
                        'method': "microsynth.microsynth.purchasing.add_or_update_item_price",
                        'args': {
                            'item_code': frm.doc.name,
                            'price_list': price_context.price_list,
                            'min_qty': values.min_qty,
                            'uom': values.uom,
                            'price_list_rate': values.price_list_rate
                        },
                        'freeze': true,
                        'callback': function () {
                            dialog.hide();
                            frappe.show_alert(
                                __("Purchasing price saved successfully"),
                                5
                            );
                        }
                    });
                }
            });
            dialog.show();
        }
    });
}


function show_add_location_dialog(frm) {
    const d = new frappe.ui.Dialog({
        'title': __("Add a Storage Location"),
        'fields': [
            {
                label: __("Subsidiary"),
                fieldname: "subsidiary",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => ({
                    filters: {
                        parent_location: ["in", ["", null]]
                    }
                }),
                default: "Balgach",
                onchange: () => {
                    // Auto-clear dependents
                    d.set_value("floor", "");
                    d.set_value("room", "");
                    d.set_value("destination", "");
                    d.set_value("rack", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Floor"),
                fieldname: "floor",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => {
                    return d.get_value("subsidiary")
                        ? { filters: { parent_location: d.get_value("subsidiary") } }
                        : {};
                },
                onchange: () => {
                    d.set_value("room", "");
                    d.set_value("destination", "");
                    d.set_value("rack", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Room"),
                fieldname: "room",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => {
                    return d.get_value("floor")
                        ? { filters: { parent_location: d.get_value("floor") } }
                        : {};
                },
                onchange: () => {
                    d.set_value("destination", "");
                    d.set_value("rack", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Destination"),
                fieldname: "destination",
                fieldtype: "Link",
                options: "Location",
                reqd: false,
                get_query: () => {
                    return d.get_value("room")
                        ? { filters: { parent_location: d.get_value("room") } }
                        : {};
                },
                onchange: () => {
                    d.set_value("rack", "");
                    refresh_field_states(d);
                }
            },
            {
                label: __("Fridge Rack"),
                fieldname: "rack",
                fieldtype: "Link",
                options: "Location",
                reqd: false,
                get_query: () => {
                    return d.get_value("destination")
                        ? { filters: { parent_location: d.get_value("destination") } }
                        : {};
                }
            },
        ],
        'primary_action_label': __("Save"),
        primary_action(values) {
            // Determine the most specific selected location
            let chosen =
                values.rack ||
                values.destination ||
                values.room ||
                values.floor ||
                values.subsidiary;

            if (!chosen) {
                frappe.msgprint(__("No location selected"));
                return;
            }

            frappe.call({
                'method': "microsynth.microsynth.purchasing.add_location_to_item",
                'args': {
                    'item': frm.doc.name,
                    'location': chosen
                },
                'callback': function (r) {
                    if (!r.exc) {
                        frm.reload_doc();
                        d.hide();
                        frappe.msgprint(__("Location added to this item."));
                    }
                }
            });
        }
    });
    d.show();

    // Initialize states: disable child fields at start
    refresh_field_states(d);
}


function refresh_field_states(d) {
    // Retrieve values
    const subsidiary = d.get_value("subsidiary");
    const floor = d.get_value("floor");
    const room = d.get_value("room");
    const destination = d.get_value("destination");

    // Enable/disable based on hierarchy
    d.get_field("floor").df.read_only = !subsidiary;
    d.get_field("room").df.read_only = !floor;
    d.get_field("destination").df.read_only = !room;
    d.get_field("rack").df.read_only = !destination;

    d.refresh();
}


function open_correct_stock_dialog(frm) {
    let d = new frappe.ui.Dialog({
        'title': "Correct Stock",
        'fields': [
            {
                fieldname: "warehouse",
                fieldtype: "Link",
                options: "Warehouse",
                label: "Warehouse",
                reqd: 1,
                default: "Stores - BAL",
                onchange: () => load_batches()
            },
            {
                fieldname: "stock_uom",
                fieldtype: "Data",
                label: "Stock UOM",
                read_only: 1,
                default: frm.doc.stock_uom
            },
            {
                fieldname: 'batch_table',
                fieldtype: 'Table',
                label: __('Batches'),
                cannot_add_rows: true,
                in_place_edit: true,
                fields: [
                    {
                        fieldname: 'batch_no',
                        fieldtype: 'Data',
                        label: __('Batch'),
                        read_only: 1,
                        in_list_view: 1,
                        columns: 3
                    },
                    {
                        fieldname: 'current_qty',
                        fieldtype: 'Float',
                        precision: 2,
                        label: __('Current Qty'),
                        read_only: 1,
                        in_list_view: 1,
                        columns: 3
                    },
                    {
                        fieldname: 'new_qty',
                        fieldtype: 'Float',
                        precision: 2,
                        label: __('New Qty'),
                        in_list_view: 1,
                        columns: 2
                    }
                ]
            }
        ],
        'primary_action_label': "Submit",
        'primary_action': function(values) {
            frappe.call({
                'method': "microsynth.microsynth.stock.correct_stock",
                'args': {
                    'item_code': frm.doc.name,
                    'warehouse': values.warehouse,
                    'rows': values.batch_table
                },
                'freeze': true,
                'freeze_message': "Correcting stock...",
                'callback': function(r) {
                    if (r.exc) {
                        frappe.msgprint(__("Error correcting stock: ") + r.exc);
                    } else {
                        frappe.msgprint(__("Stock corrected successfully."));
                    }
                    d.hide();
                    frm.reload_doc();
                }
            });
        }
    });

    function load_batches() {
        frappe.call({
            'method': "microsynth.microsynth.stock.get_batches_with_qty",
            'args': {
                'item_code': frm.doc.name,
                'warehouse': d.get_value("warehouse")
            },
            'callback': function(r) {
                // Set the data directly on the Table field's df object
                d.fields_dict.batch_table.df.data = r.message || [];

                // Refresh the grid to display updated data
                d.fields_dict.batch_table.grid.refresh();
            }
        });
    }

    d.show();
    load_batches();
}
