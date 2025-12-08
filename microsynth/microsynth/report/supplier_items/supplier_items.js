// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["Supplier Items"] = {
    "filters": [
        {
            "fieldname": "item_id",
            "label": __("Item ID"),
            "fieldtype": "Link",
            "options": "Item"
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
            "options": "Supplier"
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
    }
};


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
                reqd: 1
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
                            'account_type': 'Expense Account',
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
