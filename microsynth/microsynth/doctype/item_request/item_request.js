// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Request', {
    refresh: function(frm) {
        // Show Reject button only for Purchase Manager and Purchase User
        if (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User')) {
            if (frm.doc.docstatus === 1 && frm.doc.status === "Pending") {
                frm.add_custom_button(__('Search Item'), function() {
                    open_search_dialog(frm);
                }).addClass('btn-primary');

                frm.add_custom_button(__('Reject'), function () {
                    frappe.prompt([
                        {
                            'label': 'Reject Reason',
                            'fieldname': 'reject_reason',
                            'fieldtype': 'Small Text',
                            'reqd': 1
                        }
                    ], function(values) {
                        frappe.call({
                            'method': "microsynth.microsynth.doctype.item_request.item_request.reject_item_request",
                            'args': {
                                'item_request': frm.doc.name,
                                'reject_reason': values.reject_reason || ''
                            },
                            'callback': function(r) {
                                if (!r.exc) {
                                    frappe.show_alert({message: __('Item Request rejected'), indicator: 'red'});
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Reject Item Request'), __('Reject'));
                }).addClass('btn-danger');
            }
        }
        frm.add_custom_button(__('Material Request Overview'), function() {
            frappe.set_route('query-report', 'Material Request Overview', { reload: new Date().getTime() });
        });
    }
});


// TODO: Reduce code duplication with function open_search_dialog in material_request_overview.js
function open_search_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        'title': __('Select Purchasing Item'),
        'fields': [
            { fieldtype: 'Data', label: __('Item Name'), fieldname: 'item_name_part', default: frm.doc.item_name || '' },
            { fieldtype: 'Data', label: __('Material Code'), fieldname: 'material_code' },
            { fieldtype: 'Button', label: __('Clear Filters'), fieldname: 'clear_filters' },
            { fieldtype: 'Column Break' },
            { fieldtype: 'Data', label: __('Supplier Name'), fieldname: 'supplier_name', default: frm.doc.supplier_name || '' },
            { fieldtype: 'Data', label: __('Supplier Item Code'), fieldname: 'supplier_part_no', default: frm.doc.supplier_part_no || '' },
            { fieldtype: 'Section Break' },
            { fieldtype: 'HTML', fieldname: 'results' }
            ],
        'primary_action_label': __('Select'),
        primary_action: function(values) {
        const selected = dialog.selected_item;
        if (!selected) {
            if (document.activeElement.getAttribute('data-fieldtype') !== 'Data') {
                frappe.msgprint(__('Please select an Item'));
            }
            update_list();
            return;
        }
        dialog.hide();
        open_material_request_dialog(selected, frm);
        }
    });

    dialog.show();

    setTimeout(() => {
        const modals = document.getElementsByClassName('modal-dialog');
        if (modals.length) modals[modals.length -1].style.width = '1200px';
    }, 300);

    const f = dialog.fields_dict;
    dialog.selected_item = null;

    f.clear_filters.$input.addClass('btn-secondary').on('click', () => {
        ['item_name_part','material_code','supplier_name','supplier_part_no'].forEach(fn => f[fn].set_value(''));
        f.results.$wrapper.html(`<div class="text-muted">${__('Set at least one filter and press Enter to see results. All filters are applied together (AND-linked). Start with a broad search and refine it if necessary.')}</div>`);
        dialog.selected_item = null;
    });

    function update_list() {
        const filters_set = ['item_name_part','material_code','supplier_name','supplier_part_no']
        .some(fn => f[fn].get_value());
        if (!filters_set) {
        f.results.$wrapper.html(`<div class="text-muted">${__('Set at least one filter and press Enter to see results. All filters are applied together (AND-linked). Start with a broad search and refine it if necessary.')}</div>`);
        return;
        }
        frappe.call({
        'method': 'microsynth.microsynth.purchasing.get_purchasing_items',
        'args': {
            'item_name_part': f.item_name_part.get_value(),
            'material_code': f.material_code.get_value(),
            'supplier_name': f.supplier_name.get_value(),
            'supplier_part_no': f.supplier_part_no.get_value()
        },
        callback: function(r) {
            const items = r.message || [];
            if (!items.length) {
            f.results.$wrapper.html(`
                <div class="alert alert-info">
                ${__('No matching items found.')}
                <br><button class="btn btn-primary" id="new-purchasing-item">${__('New Purchasing Item')}</button>
                </div>
            `);
            setTimeout(() => {
                f.results.$wrapper.find('#new-purchasing-item').on('click', () => {
                    dialog.hide();
                    create_new_supplier_item(frm);
                });
            }, 0);
            return;
            }

            let html = `
                <table class="table table-bordered table-hover">
                    <thead>
                        <tr>
                            <th>${__('Select')}</th>
                            <th>${__('Item')}</th>
                            <th>${__('Item Name')}</th>
                            <th>${__('Pack Size')}</th>
                            <th>${__('Pack UOM')}</th>
                            <th>${__('Material Code')}</th>
                            <th>${__('Supplier')}</th>
                            <th>${__('Supplier Name')}</th>
                            <th>${__('Supplier Item Code')}</th>
                        </tr>
                    </thead>
                    <tbody>
                `;
            items.forEach(it => {
            html += `
                <tr>
                <td><input type="radio" name="select_item" value="${it.name}"></td>
                <td>${frappe.utils.escape_html(it.name)}</td>
                <td>${frappe.utils.escape_html(it.item_name||'')}</td>
                <td>${frappe.utils.escape_html(it.pack_size || 1)}</td>
                <td>${frappe.utils.escape_html(it.pack_uom || it.stock_uom)}</td>
                <td>${frappe.utils.escape_html(it.material_code||'')}</td>
                <td>${frappe.utils.escape_html(it.supplier||'')}</td>
                <td>${frappe.utils.escape_html(it.supplier_name||'')}</td>
                <td>${frappe.utils.escape_html(it.supplier_part_no||'')}</td>
                </tr>`;
            });
            html += '</tbody></table>';
            f.results.$wrapper.html(html);
            f.results.$wrapper.find('input[type=radio][name=select_item]').on('change', function() {
            dialog.selected_item = items.find(i => i.name === $(this).val());
            });
        }
        });
    }

    ['item_name_part','material_code','supplier_name','supplier_part_no'].forEach(fn => {
        f[fn].$input.on('change', update_list);
    });

    update_list();
}


function open_material_request_dialog(selected, frm) {
    // TODO: Rework according to material_request_overview.js and reduce code duplication
    const today = frappe.datetime.nowdate();

    let d = new frappe.ui.Dialog({
        'title': __('Material Request'),
        'fields': [
            { fieldtype: 'Data', label: __('Item Name'), fieldname: 'item_name', read_only: 1, default: selected.item_name },
            { fieldtype: 'Section Break' },
            { fieldtype: 'Data', label: __('Item Code'), fieldname: 'item_code', read_only: 1, default: selected.name },
            { fieldtype: 'Data', label: __('Supplier'), fieldname: 'supplier', read_only: 1, default: selected.supplier },
            { fieldtype: 'Int', label: __('Quantity'), fieldname: 'qty', reqd: 1, default: frm.doc.qty, min: 1 },
            { fieldtype: 'Link', label: __('Currency'), fieldname: 'currency', options: 'Currency', default: frm.doc.currency || '' },
            { fieldtype: 'Date', label: __('Required By'), fieldname: 'schedule_date', default: frm.doc.schedule_date, reqd: 1 },
            { fieldtype: 'Column Break' },
            { fieldtype: 'Data', label: __('Supplier Item Code'), fieldname: 'supplier_part_no', read_only: 1, default: selected.supplier_part_no },
            { fieldtype: 'Data', label: __('Supplier Name'), fieldname: 'supplier_name', read_only: 1, default: selected.supplier_name },
            { fieldtype: 'Data', label: __('Material Code'), fieldname: 'material_code', read_only: 1, default: selected.material_code },
            { fieldtype: 'Currency', label: __('Rate'), fieldname: 'rate', default: frm.doc.rate || 0 },
            { fieldtype: 'Link', label: __('Company'), fieldname: 'company', reqd: 1, options: 'Company', default: frm.doc.company },
            { fieldtype: 'Section Break' },
            { fieldtype: 'Small Text', label: __('Comment'), fieldname: 'comment', default: frm.doc.comment || '' }
        ],
        'primary_action_label': __('Create & Submit'),
        primary_action(values) {
            if (values.schedule_date < today) {
                frappe.msgprint(__('Required By date must be today or later'));
                return;
            }
            d.hide();
            frappe.call({
                'method': 'microsynth.microsynth.purchasing.create_mr_from_item_request',
                'args': {
                    'item_request_id': frm.doc.name,
                    'item': {
                        'item_code': selected.name,
                        'qty': values.qty,
                        'schedule_date': values.schedule_date,
                        'company': values.company,
                        'supplier': selected.supplier,
                        'supplier_name': selected.supplier_name,
                        'supplier_part_no': selected.supplier_part_no,
                        'material_code': selected.material_code,
                        'item_name': selected.item_name,
                        'currency': values.currency || 'CHF',
                        'rate': values.rate || 0,
                        'comment': values.comment || '',
                        'requested_by': frm.doc.owner
                    }
                },
                callback(r) {
                    if (!r.exc && r.message) {
                        // frappe.msgprint({
                        //     'title': __('Success'),
                        //     'indicator': 'green',
                        //     'message': __('Material Request {0} created', [
                        //         `<a href="/desk#Form/Material Request/${r.message}" target="_blank">${r.message}</a>`
                        //     ])
                        // });
                        frappe.show_alert({
                            message: __('Material Request {0} created', [
                                `<a href="/desk#Form/Material Request/${r.message}" target="_blank">${r.message}</a>`
                            ]),
                            indicator: 'green'
                        });
                        cur_frm.reload_doc();
                    }
                }
            });
        }
    });

    d.show();

    // Force wider dialog
    setTimeout(() => {
        let modals = document.getElementsByClassName('modal-dialog');
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = '800px';
        }
    }, 400);
}


// TODO: Reduce code duplication with function create_new_supplier_item in supplier_items.js
function create_new_supplier_item(frm) {
    let dialog = new frappe.ui.Dialog({
        'title': 'New Purchasing Item',
        'fields': [
            {
                label: 'Item Name',
                fieldname: 'item_name',
                fieldtype: 'Data',
                reqd: 1,
                default: frm.doc.item_name || ''
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
                reqd: 1,
                min: 0.0001
            },
            {
                label: 'Pack Size of one stock unit',
                fieldname: 'pack_size',
                fieldtype: 'Float',
                //description: 'How much does a stock unit contain?',
                reqd: 1,
                default: frm.doc.pack_size,
                min: 0.0001
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Stock Unit of Measure (UOM)',
                fieldname: 'stock_uom',
                fieldtype: 'Link',
                options: 'UOM',
                reqd: 1,
                default: frm.doc.stock_uom,
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
                reqd: 1,
                default: frm.doc.pack_uom
            },
            // --- One Item Default ---
            { fieldtype: 'Section Break' },
            {
                label: 'Company',
                fieldname: 'company',
                fieldtype: 'Link',
                options: 'Company',
                default: frm.doc.company || 'Microsynth AG',
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
                default: frm.doc.supplier,
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
                default: frm.doc.supplier,
                onchange: function () {
                    if (!dialog.get_value('default_supplier')) {
                        dialog.set_value('default_supplier', dialog.get_value('supplier'));
                    }
                }
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Supplier Item Code',
                fieldname: 'supplier_part_no',
                fieldtype: 'Data',
                reqd: 1,
                default: frm.doc.supplier_part_no || '',
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
                description: 'Default Purchase Unit of Measure',
                default: frm.doc.uom || frm.doc.stock_uom,
                // get_query: function () {
                //     return {
                //         'filters': [
                //             ['name', 'NOT IN', ['Reaction Units', 'L', 'kg', 'g', 'h', 'µmol', 'cm', 'm', 'µl', 'ml', 'ng', 'µg', 'mg']]
                //         ]
                //     }
                // }
            },
            { fieldtype: 'Column Break' },
            {
                label: 'Conversion Factor',
                fieldname: 'conversion_factor',
                fieldtype: 'Float',
                description: 'Factor to convert from purchase to stock UOM',
                default: frm.doc.conversion_factor,
                min: 1
            }
        ],
        'primary_action_label': 'Create',
        primary_action(values) {
            frappe.call({
                'method': 'microsynth.microsynth.report.supplier_items.supplier_items.create_purchasing_item',
                'args': { data: values },
                'callback': function (r) {
                    if (!r.exc && r.message) {
                        const item_code = r.message;
                        // frappe.msgprint({
                        //     'title': __('Item Created'),
                        //     'message': __('Item created: {0}', [`${item_code}`]),
                        //     'indicator': 'green'
                        // });
                        frappe.show_alert({
                            message: __('Item created: {0}', [`${item_code}`]),
                            indicator: 'green'
                        });
                        dialog.hide();

                        // Fetch full item details and open MR dialog
                        frappe.call({
                            'method': 'frappe.client.get',
                            'args': {
                                'doctype': 'Item',
                                'name': item_code
                            },
                            callback: function (res) {
                                const item = res.message;
                                const selected = {
                                    'name': item.name,
                                    'item_name': item.item_name,
                                    'supplier': values.supplier,
                                    'supplier_name': values.default_supplier,
                                    'supplier_part_no': values.supplier_part_no,
                                    'material_code': values.material_code
                                };
                                open_material_request_dialog(selected, frm);
                            }
                        });
                    }
                }
            });
        }
    });

    // Get next item code
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
