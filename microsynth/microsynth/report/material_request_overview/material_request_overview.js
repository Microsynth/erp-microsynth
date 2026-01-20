// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["Material Request Overview"] = {
    "filters": [
        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "Link",
            options: "Supplier"
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: "Microsynth AG"
        },
		{
			fieldname: "mode",
			label: __("Mode"),
			fieldtype: "Select",
			options: "To Order\nUnreceived Material Requests\nAll Material Requests",
			default: (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User'))
                ? "To Order"
                : "All Material Requests"
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -365), // Default to one year ago
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
        {
            fieldname: "qm_process",
            label: __("QM Process"),
            fieldtype: "Link",
            options: "QM Process"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();

        report.page.add_inner_button( __("New Request"), function() {
            // open search dialog currently shown on Material Request (Button "Add Item")
            open_search_dialog(report);
        }).addClass("btn-primary");

        if (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User')) {
            report.page.add_inner_button( __("Create Purchase Order"), function() {
                create_purchase_order(frappe.query_report.get_filter_values(), frappe.query_report);
            }).addClass("btn-primary");
        }
    },
    'formatter': function(value, row, column, data, default_formatter) {
        // For Item Request rows, show item_name as plain text (no link)
        if (column.fieldname === "item_code" && data.request_type === "Item Request") {
            return data.item_name || value || "";
        }
        return default_formatter(value, row, column, data);
    },
    'after_datatable_render': function(report) {
        // After the report is rendered, apply background color to rows based on request_type
        var elements= document.querySelectorAll('[data-row-index][data-indent="0"]');
        elements.forEach(function(row, index) {
            var rowColor = (frappe.query_report.data[index].request_type === "Item Request") ? '#eeeeee' : '';
            var cells = row.querySelectorAll('div');
            cells.forEach(function(cell) {
                cell.style.backgroundColor = rowColor;
            });
        });
    }
};


function create_purchase_order(filters, report) {
	if (filters.mode !== "To Order") {
		frappe.msgprint( __("Please set the Mode filter to 'To Order'"), __("Validation") );
		return;
	}
    if (!filters.supplier) {
        // Build unique list of suppliers from report data
        const supplierMap = {};
        (report.data || []).forEach(row => {
            if (row && row.supplier) {
                supplierMap[String(row.supplier)] = row.supplier_name || '';
            }
        });
        const suppliers = Object.keys(supplierMap);

        if (suppliers.length === 0) {
            frappe.msgprint(__('No Supplier found in report data. Please set the Supplier filter or ensure the report contains suppliers.'), __('Validation'));
            return;
        }

        // If exactly one supplier, preselect and continue
        if (suppliers.length === 1) {
            filters.supplier = suppliers[0];
            // continue to create PO below
        } else {
            // Show dialog to choose one supplier
            const rows = suppliers.map(s => {
                return `
                    <tr>
                        <td style="vertical-align:middle"><input type="radio" name="choose_supplier" value="${frappe.utils.escape_html(s)}"></td>
                        <td style="vertical-align:middle">${frappe.utils.escape_html(s)}</td>
                        <td style="vertical-align:middle">${frappe.utils.escape_html(supplierMap[s] || '')}</td>
                    </tr>`;
            }).join('');

            const html = `
                <div class="help-block">${__('Which supplier would you like to order from?')}</div>
                <table class="table table-bordered table-hover">
                    <thead>
                        <tr><th>${__('Select')}</th><th>${__('Supplier')}</th><th>${__('Supplier Name')}</th></tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>`;

            const dlg = new frappe.ui.Dialog({
                'title': __('Choose Supplier'),
                'fields': [ {
                    'fieldtype': 'HTML',
                    'fieldname': 'suppliers_html'
                } ],
                'primary_action_label': __('Choose'),
                'primary_action'(values) {
                    const selected = dlg.$wrapper.find('input[name=choose_supplier]:checked').val();
                    if (!selected) {
                        frappe.msgprint(__('Please select a Supplier'));
                        return;
                    }
                    dlg.hide();
                    // set chosen supplier and retry PO creation
                    filters.supplier = selected;
                    create_purchase_order(filters, report);
                }
            });
            dlg.show();
            dlg.fields_dict.suppliers_html.$wrapper.html(html);
            return;
        }
    }
    // Check for pending Item Requests in report data
    const pendingItemRequests = (report.data || []).filter(row =>
        row.request_type === "Item Request" &&
        row.supplier === filters.supplier
    );
    if (pendingItemRequests.length > 0) {
        frappe.msgprint(__("There are {0} pending Item Requests for this Supplier. Please treat them first.", [pendingItemRequests.length]), __("Warning"));
        return;
    }

    // Proceed with PO creation
    frappe.call({
        'method': "microsynth.microsynth.purchasing.create_po_from_open_mr",
        'args': {
            'filters': filters
        },
        'freeze': true,
        'freeze_message': 'Creating Purchase Order, please be patient.',
        'callback': function(r) {
            if (r.message) {
                frappe.set_route("Form", "Purchase Order", r.message);
            } else {
                frappe.show_alert("Internal Error");
            }
        }
    });
}


function open_search_dialog(report) {
    let dialog = new frappe.ui.Dialog({
        'title': __('Select Purchasing Item'),
        'fields': [
            {fieldtype:'Data', label: __('Item Name'), fieldname:'item_name_part'},
            {fieldtype:'Data', label: __('Material Code'), fieldname:'material_code'},
            {fieldtype:'Button', label: __('Clear Filters'), fieldname:'clear_filters'},
            {fieldtype:'Column Break'},
            {fieldtype:'Data', label: __('Supplier Name'), fieldname:'supplier_name'},
            {fieldtype:'Data', label: __('Supplier Item Code'), fieldname:'supplier_part_no'},
            {fieldtype:'Section Break'},
            {fieldtype:'HTML', fieldname:'results'}
        ],
        'primary_action_label': __('Select'),
        primary_action: function(values) {
            const selected = dialog.selected_item;
            if (!selected) {
                if (document.activeElement.getAttribute('data-fieldtype') !== 'Data') {
                    frappe.msgprint(__('Please select one Item'));
                }
                update_list();
                return;
            }
            // Check if the Supplier has either no substitute_status or substitute_status "Verified".
            // If not, show an error that the purchasing department should be contacted.
            if (
                selected.substitute_status &&
                selected.substitute_status !== 'Verified'
            ) {
                frappe.msgprint({
                    'title': __('Material Request not allowed'),
                    'indicator': 'red',
                    'message': __(
                        'The Supplier {0}: {1} has Substitute Status <b>{2}</b> for Item {3}: {4}.<br><br>' +
                        'Material Requests are only allowed if the Supplier has substitute status ' +
                        '"Verified" or no substitute status for the Item.<br><br>' +
                        'Please select another combination of Item and Supplier or contact the Purchasing department.',
                        [
                            selected.supplier,
                            selected.supplier_name,
                            selected.substitute_status,
                            selected.name,
                            selected.item_name
                        ]
                    )
                });
                return;
            }
            dialog.hide();
            // Show confirmation dialog with qty, schedule_date, company
            open_confirmation_dialog(selected, report);
        }
    });
    dialog.show();

    // Force wider dialog
    setTimeout(() => {
        let modals = document.getElementsByClassName('modal-dialog');
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = '1400px';
        }
    }, 300);

    const f = dialog.fields_dict;
    dialog.selected_item = null;

    f.results.$wrapper.on('click.request_item', '#request-item-btn', function () {
        const $btn = $(this);
        $btn.prop('disabled', true);
        dialog.hide();
    });

    // Clear filters button
    f.clear_filters.$input.addClass('btn-secondary');
    f.clear_filters.$input.on('click', () => {
        ['item_name_part','material_code','supplier_name','supplier_part_no'].forEach(fn => {
            f[fn].set_value('');
        });
        f.results.$wrapper.html('<div class="text-muted">' + __('Set at least one filter and press Enter to see results. All filters are applied together (AND-linked). Start with a broad search and refine it if necessary.') + '</div>');
        dialog.selected_item = null;
    });

    function update_list() {
        // check if any filter set
        const filters_set = ['item_name_part','material_code','supplier_name','supplier_part_no'].some(fn => f[fn].get_value());
        if (!filters_set) {
            f.results.$wrapper.html('<div class="text-muted">' + __('Set at least one filter to see results. All filters are applied together (AND-linked). Start with a broad search and refine it if necessary.') + '</div>');
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
            'callback': function(r) {
                const items = r.message || [];
                const variantMap = {};
                items.forEach(it => {
                    const key = `${it.name}::${it.supplier || ''}`;
                    variantMap[key] = it;
                });
                dialog._variantMap = variantMap;
                if (items.length === 0) {
                    // No results but filters set -> show "Request Item" button
                    f.results.$wrapper.html(`
                        <div class="alert alert-info">
                            ${__('No matching items found.')}
                            <br>
                            <button type="button"
                                    class="btn btn-primary"
                                    id="request-item-btn">
                                ${__('Request Item')}
                            </button>
                        </div>
                    `);

                    // Now attach the click listener AFTER the button exists
                    f.results.$wrapper
                    .find('#request-item-btn')
                    .off('click')
                    .on('click', function (e) {
                        e.preventDefault();
                        e.stopPropagation();

                        dialog.hide();
                        open_item_request_dialog(
                            report,
                            f.item_name_part.get_value(),
                            f.supplier_name.get_value(),
                            f.supplier_part_no.get_value()
                        );
                    });

                    dialog.selected_item = null;
                    return;
                }
                // Build table html for results
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
                                <th>${__('Last Purchase Rate [CHF]')}</th>
                                <th>${__('Last Order Date')}</th>
                                <th>${__('Supplier')}</th>
                                <th>${__('Supplier Item Code')}</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                items.forEach(it => {
                    const key = `${it.name}::${it.supplier || ''}`;

                        html += `
                            <tr>
                                <td>
                                    <input type="radio"
                                        name="select_item"
                                        value="${frappe.utils.escape_html(key)}">
                                </td>
                                <td>${frappe.utils.escape_html(it.name)}</td>
                                <td>${frappe.utils.escape_html(it.item_name || '')}</td>
                                <td>${frappe.utils.escape_html(it.pack_size || 1)}</td>
                                <td>${frappe.utils.escape_html(it.pack_uom || it.stock_uom)}</td>
                                <td>${frappe.utils.escape_html(it.material_code || '')}</td>
                                <td style="text-align: right;">
                                    ${frappe.utils.escape_html(it.last_purchase_rate || '')}
                                </td>
                                <td>
                                    ${it.last_order_date
                                        ? frappe.datetime.str_to_user(it.last_order_date)
                                        : ''}
                                </td>
                                <td>
                                    ${frappe.utils.escape_html(it.supplier || '')}:
                                    ${frappe.utils.escape_html(it.supplier_name || '')}
                                    ${it.substitute_status
                                        ? ` (${frappe.utils.escape_html(it.substitute_status)})`
                                        : ''}
                                </td>
                                <td>${frappe.utils.escape_html(it.supplier_part_no || '')}</td>
                            </tr>
                        `;
                });
                html += '</tbody></table>';
                const max_display_rows = 10;
                if (items.length >= max_display_rows) {
                    html += `
                        <div class="text-muted">
                            ${__('Showing only the first {0} results, but there could be more. Please specify your search.', [max_display_rows])}
                        </div>
                    `;
                }
                f.results.$wrapper.html(html);

                f.results.$wrapper
                    .find('input[type=radio][name=select_item]')
                    .on('change', function () {
                        const key = $(this).val();
                        dialog.selected_item = dialog._variantMap[key];
                    });
            }
        });
    }

    ['item_name_part','material_code','supplier_name','supplier_part_no']
        .forEach(fn => {
            f[fn].$input.on('input', frappe.utils.debounce(update_list, 300));
        });

    update_list();
}


// Confirmation dialog after selecting an item
function open_confirmation_dialog(selected, report) {
    const today = frappe.datetime.nowdate();

    // Compute schedule_date default: If lead_time_days is set, use today + lead_time_days, otherwise today + 30 days
    const default_schedule_date = frappe.datetime.add_days(
        today,
        selected.lead_time_days ? cint(selected.lead_time_days) : 30
    );

    // Compute conversion info: If purchase_uom and stock_uom differ, display conversion text
    let conversion_info = '';
    if (selected.purchase_uom && selected.stock_uom && selected.purchase_uom !== selected.stock_uom) {
        const cf = selected.conversion_factor || 1;
        let stock_uom = selected.stock_uom || "";
        let plural = stock_uom.toLowerCase().endsWith("s") ? "" : "(s)";
        conversion_info = __(
            '1 {0} = {1} {2}{3}',
            [
                selected.purchase_uom,
                cf,
                stock_uom,
                plural
            ]
        );
    }
    // try to mimic the look of a read-only frappe field for the conversion info
    const conversion_field = conversion_info
        ? {
            fieldtype: 'HTML',
            fieldname: 'conversion_html',
            options: `
                <div class="frappe-control input-max-width" style="margin-top: 3px;">
                    <label class="control-label" style="display:block; margin-bottom:5px;">${__('Conversion')}</label>
                    <div class="control-value like-disabled-input" style="
                        display:block;
                        width:100%;
                        padding:6px 8px;
                        min-height:28px;
                        line-height:1.42857143;
                        color:#495057;
                        background-color:#f4f5f6;
                        border-radius:4px;
                        font-size:13px;
                        white-space:nowrap;
                        overflow:hidden;
                        text-overflow:ellipsis;
                    ">
                        ${frappe.utils.escape_html(conversion_info)}
                    </div>
                </div>`
        }
        : null;

    let d = new frappe.ui.Dialog({
        'title': __('Confirm Material Request'),
        'fields': [
            { fieldtype: 'Data', label: __('Item Name'), fieldname: 'item_name', read_only: 1, default: selected.item_name },
            { fieldtype: 'Data', label: __('Supplier Name'), fieldname: 'supplier_name', read_only: 1, default: selected.supplier_name },

            { fieldtype: 'Section Break' },

            { fieldtype: 'Data', label: __('Supplier'), fieldname: 'supplier', read_only: 1, default: selected.supplier },
            { fieldtype: 'Data', label: __('Material Code'), fieldname: 'material_code', read_only: 1, default: selected.material_code },
            { fieldtype: 'Int', label: __('Quantity regarding Purchase UOM'), fieldname: 'qty', reqd: true, default: 1, min: 1 },
            { fieldtype: 'Data', label: __('Stock UOM'), fieldname: 'stock_uom', read_only: 1, default: selected.stock_uom },


            { fieldtype: 'Column Break' },

            { fieldtype: 'Data', label: __('Supplier Item Code'), fieldname: 'supplier_part_no', read_only: 1, default: selected.supplier_part_no },
            { fieldtype: 'Link', label: __('Company'), fieldname: 'company', reqd: true, options: 'Company', default: frappe.defaults.get_default('company') },
            { fieldtype: 'Data', label: __('Purchase UOM'), fieldname: 'purchase_uom', read_only: 1, default: selected.purchase_uom || selected.stock_uom },
            { fieldtype: 'Data', label: __('Pack Size and Pack UOM'), fieldname: 'pack_size_uom', read_only: 1, description: 'How much does 1 stock unit contain?', default: (selected.pack_size || 1) + " " + (selected.pack_uom || selected.stock_uom) },

            { fieldtype: 'Column Break' },

            { fieldtype: 'Data', label: __('Microsynth Item Code'), fieldname: 'item_code', read_only: 1, default: selected.name },
            { fieldtype: 'Date', label: __('Required by'), fieldname: 'schedule_date', reqd: true, default: default_schedule_date },
            ...(conversion_field ? [conversion_field] : []),
            { fieldtype: 'HTML', fieldname: 'order_preview' },

            { fieldtype: 'Section Break' },

            { fieldtype: 'Small Text', label: __('Comment'), fieldname: 'comment' }
        ],
        'primary_action_label': __('Create & Submit'),
        primary_action(values) {
            if (values.schedule_date < today) {
                frappe.msgprint(__('Required By date must be today or later'));
                return;
            }
            frappe.call({
                'method': "microsynth.microsynth.purchasing.create_material_request",
                'args': {
                    'item_code': selected.name,
                    'qty': values.qty,
                    'schedule_date': values.schedule_date,
                    'company': values.company,
                    'comment': values.comment || '',
                    'supplier': values.supplier
                },
                callback(r) {
                    if (!r.exc && r.message) {
                        const link = `<a href="/desk#Form/Material Request/${r.message}" target="_blank">${r.message}</a>`;
                        frappe.show_alert({message: __('Material Request created and submitted: {0}', [link]), indicator: 'green'});
                        d.hide();
                        report.refresh();
                    }
                }
            });
        }
    });
    d.show();

    function update_order_preview() {
        const qty = cint(d.get_value('qty')) || 0;
        const cf = selected.conversion_factor || 1;
        const pack_size = selected.pack_size || 1;
        const pack_uom = selected.pack_uom || selected.stock_uom || '';

        const total = qty * cf * pack_size;

        const text = __(
            '<b>{0} × {1} × {2} = {3} {4}</b>',
            [qty, cf, pack_size, total, pack_uom]
        );

        d.fields_dict.order_preview.$wrapper.html(`
            <div class="frappe-control input-max-width" style="margin-top:6px;">
                <label class="control-label" style="display:block; margin-bottom:4px;">
                    ${__('You are going to order')}
                </label>
                <div class="control-value like-disabled-input" style="
                    padding:6px 8px;
                    background:#f4f5f6;
                    border-radius:4px;
                    font-size:13px;
                ">
                    ${text}
                </div>
            </div>
        `);
    }

    d.fields_dict.qty.$input.on('input', update_order_preview);
    update_order_preview();
    // Force wider dialog
    setTimeout(() => {
        let modals = document.getElementsByClassName('modal-dialog');
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = '800px';
        }
    }, 400);
}


function open_item_request_dialog(report, item_name, supplier_name, supplier_part_no) {
    let d = new frappe.ui.Dialog({
        'title': __('New Item Request'),
        'fields': [
            // Left column
            {fieldtype:'Data', label: __('Item Name'), fieldname:'item_name', reqd: 1, default: item_name || ''},
            {fieldtype:'Link', label: __('Supplier'), fieldname:'supplier', options: 'Supplier'},
            //{fieldtype:'Currency', label: __('Rate'), fieldname:'rate'},
            {fieldtype:'Link', label: __('Company'), fieldname:'company', options: 'Company', reqd: 1, default: frappe.defaults.get_default('company')},
            {fieldtype:'Float', label: __('Quantity'), fieldname:'qty', reqd: 1, min: 0.0001},

            {fieldtype:'Column Break'},

            // Right column
            {fieldtype:'Data', label: __('Supplier Item Code'), fieldname:'supplier_part_no', default: supplier_part_no || ''},
            {fieldtype:'Data', label: __('Supplier Name'), fieldname:'supplier_name', reqd: 1, default: supplier_name || ''},
            //{fieldtype:'Link', label: __('Currency'), fieldname:'currency', options: 'Currency'},
            {fieldtype:'Date', label: __('Required by'), fieldname:'schedule_date', default: frappe.datetime.add_days(frappe.datetime.nowdate(), 30)},

            {   fieldtype:'Link',
                label: __('Stock UOM (unit of measure)'),
                fieldname:'uom',
                options: 'UOM',
                reqd: 1,
                description: 'Fixed warehouse unit used for stock movements',
                get_query: function () {
                    return {
                        'filters': [
                            ['name', 'NOT IN', ['Carton', 'Reaction Units', 'L', 'kg', 'g', 'h', 'µmol', 'cm', 'm', 'µl', 'ml', 'ng', 'µg', 'mg']]
                        ]
                    }
                }
            },

            {fieldtype:'Section Break'},

            // Full width comments
            {fieldtype:'Text', label: __('Comments'), fieldname:'comment', colspan: 2, description: 'URL to the supplier product page, price and currency, ...'}
        ],
        'primary_action_label': __('Create & Submit'),
        primary_action(values) {
            if (!values.qty || values.qty <= 0) {
                frappe.msgprint(__('Quantity must be greater than zero.'));
                return;
            }
            frappe.call({
                'method': "microsynth.microsynth.report.material_request_overview.material_request_overview.create_item_request",
                'args': { 'data': values },
                callback(r) {
                    if (!r.exc) {
                        const link = `<a href="/desk#Form/Item Request/${r.message}" target="_blank">${r.message}</a>`;
                        frappe.msgprint({
                          title: __('Success'),
                          indicator: 'green',
                          message: __('Item Request created and submitted: {0}', [link])
                        });
                        d.hide();
                        report.refresh();
                    }
                }
            });
        }
    });
    d.show();
    // Fetch Supplier Name if Supplier is set but not Supplier Name
    d.fields_dict.supplier.df.onchange = function() {
        const supplier = d.get_value('supplier');
        const current_name = d.get_value('supplier_name');

        if (supplier && !current_name) {
            frappe.db.get_value('Supplier', supplier, 'supplier_name')
                .then(r => {
                    if (r && r.message && r.message.supplier_name) {
                        d.set_value('supplier_name', r.message.supplier_name);
                    }
                });
        }
    };
}
