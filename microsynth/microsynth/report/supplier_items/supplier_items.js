// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["Supplier Items"] = {
    "filters": [
        {
            "fieldname": "item_id",
            "label": __("Item ID"),
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function() {
                return {
                    "filters": {
                        "item_group": "Purchasing",
                        "is_purchase_item": 1,
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "item_name",
            "label": __("Item Name"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier",
            "get_query": function() {
                return {
                    "filters": {
                        "disabled": 0
                    }
                };
            }
        },
        {
            "fieldname": "supplier_part_no",
            "label": __("Supplier Part Number"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "storage_location",
            "label": __("Storage Location"),
            "fieldtype": "Link",
            "options": "Location"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();

        report.page.add_inner_button(__('Create new'), function() {
            create_new_supplier_item();
        }).addClass("btn-primary");

        if (!locals.double_click_handler) {
            locals.double_click_handler = true;

            cur_page.container.addEventListener("dblclick", function(event) {
                let row_index = event.delegatedTarget && event.delegatedTarget.getAttribute("data-row-index");
                if (!row_index) return;

                const row_data = frappe.query_report.data[row_index];

                // Only allow editing if user has write permission
                if (!frappe.perm.has_perm("Item", 0, "write")) {
                    frappe.msgprint(__("You do not have permission to edit this item."));
                    return;
                }

                open_edit_dialog(row_data, report);
            });
        }
    }
};


function open_edit_dialog(row_data, report) {
    // Check permissions for relevant DocTypes:
    // Item and Supplier (if editing supplier fields)
    const can_edit_item = frappe.model.can_write('Item');
    const can_edit_supplier = frappe.model.can_write('Supplier');

    // Build dialog fields with readonly depending on permission
    const dialog_fields = [
        // { label: __('Item Name'), fieldname: 'item_name', fieldtype: 'Data', default: row_data.item_name, read_only: true },
        // { fieldtype: 'Section Break' },

        { label: __('Supplier Part Nr.'), fieldname: 'supplier_part_no', fieldtype: 'Data', default: row_data.supplier_part_no, read_only: !can_edit_item },
        { label: __('Supplier'), fieldname: 'supplier', fieldtype: 'Link', options: 'Supplier', default: row_data.supplier, read_only: true },
        { label: __('Purchase UOM'), fieldname: 'purchase_uom', fieldtype: 'Link', options: 'UOM', default: row_data.purchase_uom, read_only: !can_edit_item },
        { label: __('Stock UOM'), fieldname: 'stock_uom', fieldtype: 'Link', options: 'UOM', default: row_data.stock_uom, read_only: !can_edit_item,
            get_query: function () {
                return {
                    'filters': [
                        ['name', 'NOT IN', ['Carton', 'Reaction Units', 'L', 'kg', 'g', 'h', 'µmol', 'cm', 'm', 'µl', 'ml', 'ng', 'µg', 'mg']]
                    ]
                }
            }
        },
        { label: __('Price'), fieldname: 'price_list_rate', fieldtype: 'Currency', options: row_data.currency || frappe.defaults.get_default('currency'), default: row_data.price_list_rate, read_only: !can_edit_item },
        { label: __('Pack Size'), fieldname: 'pack_size', fieldtype: 'Float', default: row_data.pack_size, read_only: !can_edit_item },
        { label: __('Lead Time in Days'), fieldname: 'lead_time_days', fieldtype: 'Int', default: row_data.lead_time_days, read_only: !can_edit_item },
        { label: __('Material Code'), fieldname: 'material_code', fieldtype: 'Data', default: row_data.material_code, read_only: !can_edit_item },

        { fieldtype: 'Column Break' },

        { label: __('Microsynth Item Code'), fieldname: 'item_code', fieldtype: 'Link', options: 'Item', default: row_data.item_code, read_only: true },
        { label: __('Supplier Name'), fieldname: 'supplier_name', fieldtype: 'Data', default: row_data.supplier_name, read_only: true },
        { label: __('Conversion Factor to Stock UOM'), fieldname: 'conversion_factor', fieldtype: 'Float', default: row_data.conversion_factor, read_only: !can_edit_item },
        { label: __('Safety Stock'), fieldname: 'safety_stock', fieldtype: 'Float', default: row_data.safety_stock, read_only: !can_edit_item },
        { label: __('Min Order Qty'), fieldname: 'min_order_qty', fieldtype: 'Float', default: row_data.min_order_qty, read_only: !can_edit_item },
        { label: __('Pack UOM'), fieldname: 'pack_uom', fieldtype: 'Link', options: 'UOM', default: row_data.pack_uom, read_only: !can_edit_item },
        { label: __('Shelf Life Years'), fieldname: 'shelf_life_in_years', fieldtype: 'Float', default: row_data.shelf_life_in_years, read_only: !can_edit_item },
        { label: __('Substitute Status'), fieldname: 'substitute_status', fieldtype: 'Select', options: '\nPotential\nVerified\nDiscontinued\nBlocked', default: row_data.substitute_status, read_only: !can_edit_item, description: 'blocked = not allowed to use; discontinued = no longer available from the supplier' },

        { fieldtype: 'Section Break' },

        { label: __('Location(s)'), fieldname: 'locations', fieldtype: 'Data', default: row_data.locations, read_only: true }
    ];

    let dialog = new frappe.ui.Dialog({
        title: __('Edit Supplier Item (Beta-Mode, check carefully)'),
        fields: dialog_fields,
        primary_action_label: __('Save'),
        primary_action(values) {
            save_supplier_item(row_data, values, dialog, report);
        }
    });

    dialog.show();
}

function save_supplier_item(original_row, values, dialog, report) {
    // Prepare data to update
    // Mainly update Item fields (Item doc) and Supplier Item child

    let updates = {
        item_code: original_row.item_code,
        material_code: values.material_code,
        pack_size: values.pack_size,
        pack_uom: values.pack_uom,
        purchase_uom: values.purchase_uom,
        conversion_factor: values.conversion_factor,
        stock_uom: values.stock_uom,
        safety_stock: values.safety_stock,
        lead_time_days: values.lead_time_days,
        shelf_life_in_years: values.shelf_life_in_years,
        shelf_life_in_days: values.shelf_life_in_days,
        min_order_qty: values.min_order_qty,
        substitute_status: values.substitute_status,
        price_list_rate: values.price_list_rate,
        // Supplier Item child fields
        supplier: values.supplier,
        supplier_part_no: values.supplier_part_no,
    };

    frappe.call({
        'method': "microsynth.microsynth.report.supplier_items.supplier_items.update_supplier_item",
        'args': {
            'data': updates
        },
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({message: __('Supplier Item updated'), indicator: 'green'});
                dialog.hide();
                report.refresh();
            } else {
                frappe.msgprint({message: __('Failed to update Supplier Item'), indicator: 'red'});
                dialog.enable_primary_action();
            }
        }
    });
}


// TODO: Reduce code duplication with function create_new_supplier_item in item_request.js
function create_new_supplier_item() {
    let dialog = new frappe.ui.Dialog({
        'title': 'New Purchasing Item',
        'fields': [
            {
                label: 'Item Name',
                fieldname: 'item_name',
                fieldtype: 'Data',
                reqd: 1
            },
            { fieldtype: 'Section Break' },
            {
                label: 'Internal Code',
                fieldname: 'internal_code',
                fieldtype: 'Data',
                reqd: 0,
                description: 'Optional 4-digit "EAN" code',
                maxlength: 4
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Item Code',
                fieldname: 'item_code',
                fieldtype: 'Data',
                reqd: 1,
                read_only: 1
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Material Code',
                fieldname: 'material_code',
                fieldtype: 'Data',
                reqd: 0,
                description: 'Oligo Modification Code / Slims Content Type',
            },
            { fieldtype: 'Section Break' },
            {
                label: 'Shelf Life in Years',
                fieldname: 'shelf_life_in_years',
                fieldtype: 'Float',
                reqd: 1
            },
            {
                label: 'Pack Size of one stock unit',
                fieldname: 'pack_size',
                fieldtype: 'Float',
                //description: 'How much does a stock unit contain?',
                reqd: 1
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Stock Unit of Measure (UOM)',
                fieldname: 'stock_uom',
                fieldtype: 'Link',
                options: 'UOM',
                reqd: 1,
                get_query: function () {
                    return {
                        'filters': [
                            ['name', 'NOT IN', ['Carton', 'Reaction Units', 'L', 'kg', 'g', 'h', 'µmol', 'cm', 'm', 'µl', 'ml', 'ng', 'µg', 'mg']]
                        ]
                    }
                }
            },
            {
                label: 'Pack UOM',
                fieldname: 'pack_uom',
                fieldtype: 'Link',
                options: 'UOM',
                reqd: 1
            },
            // --- One Item Default ---
            { fieldtype: 'Section Break' },
            {
                label: 'Company',
                fieldname: 'company',
                fieldtype: 'Link',
                options: 'Company',
                default: 'Microsynth AG',
                reqd: 1
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Default Expense Account',
                fieldname: 'expense_account',
                fieldtype: 'Link',
                reqd: 1,
                options: 'Account',
                description: '"Kostenstelle"',
                get_query: function () {
                    return {
                        'filters': {
                            'disabled': 0,
                            'root_type': 'Expense',
                            'is_group': 0,
                            'company': dialog.get_value('company') || 'Microsynth AG'
                        }
                    };
                }
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Default Supplier',
                fieldname: 'default_supplier',
                fieldtype: 'Link',
                reqd: 1,
                options: 'Supplier',
                onchange: function () {
                    if (!dialog.get_value('supplier')) {
                        dialog.set_value('supplier', dialog.get_value('default_supplier'));
                    }
                }
            },
            // --- One Supplier Entry ---
            { fieldtype: 'Section Break', label: 'Supplier Item' },
            {
                label: 'Supplier',
                fieldname: 'supplier',
                fieldtype: 'Link',
                reqd: 1,
                options: 'Supplier',
                onchange: function () {
                    if (!dialog.get_value('default_supplier')) {
                        dialog.set_value('default_supplier', dialog.get_value('supplier'));
                    }
                }
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Supplier Part Number',
                fieldname: 'supplier_part_no',
                fieldtype: 'Data',
                reqd: 1
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Substitute Status',
                fieldname: 'substitute_status',
                fieldtype: 'Select',
                description: 'blocked = not allowed to use; discontinued = no longer available from the Supplier',
                options: '\nPotential\nVerified\nDiscontinued\nBlocked'
            },
            // --- One UOM Conversion ---
            { fieldtype: 'Section Break' },
            {
                label: 'Purchase UOM',
                fieldname: 'purchase_uom',
                fieldtype: 'Link',
                options: 'UOM',
                description: 'Default Purchase Unit of Measure'
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Conversion Factor',
                fieldname: 'conversion_factor',
                fieldtype: 'Float',
                description: 'Factor to convert from purchase to stock UOM'
            }
        ],
        'primary_action_label': 'Create',
        primary_action(values) {
            frappe.call({
                'method': 'microsynth.microsynth.report.supplier_items.supplier_items.create_purchasing_item',
                'args': {
                    'data': values
                },
                'callback': function(r) {
                    if (!r.exc) {
                        const link = frappe.utils.get_form_link('Item', r.message);
                        frappe.msgprint({
                            'title': __('Item Created'),
                            'message': __('Item created: {0}<br>Please add its Storage Location(s), Safety Stock, Lead Time in days, Minimum Order Qty, etc. if necessary.', [`<a href="${link}" target="_blank">${r.message}</a>`]),
                            'indicator': 'green'
                        });
                        dialog.hide();
                    }
                }
            });
        }
    });

    // Handle internal_code -> item_code auto-fill
    dialog.fields_dict.internal_code.$input.on('change', function () {
        const code = dialog.get_value('internal_code');
        if (code && code.match(/^\d{4}$/)) {
            dialog.set_value('item_code', 'P00' + code);
        } else {
            frappe.call({
                'method': 'microsynth.microsynth.naming_series.get_next_purchasing_item_id',
                'callback': function (r) {
                    dialog.set_value('item_code', r.message);
                }
            });
        }
    });

    dialog.show();

    // Trigger auto-fill on open
    frappe.call({
        'method': 'microsynth.microsynth.naming_series.get_next_purchasing_item_id',
        'callback': function (r) {
            dialog.set_value('item_code', r.message);
        }
    });
}
