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
			options: "Open Requests\nAll Material Requests",
			default: "Open Requests"
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
            console.log("Row " + index + ": ", row);
            var rowColor = (frappe.query_report.data[index].request_type === "Item Request") ? '#eeeeee' : '';
            var cells = row.querySelectorAll('div');
            cells.forEach(function(cell) {
                cell.style.backgroundColor = rowColor;
            });
        });
    }
};


function create_purchase_order(filters, report) {
    if (!filters.supplier) {
        frappe.msgprint( __("Please set the Supplier filter"), __("Validation") );
        return;
    }
	if (filters.mode !== "Open Requests") {
		frappe.msgprint( __("Please set the Mode filter to 'Open Requests'"), __("Validation") );
		return;
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

    // No pending Item Requests, proceed with PO creation
    frappe.call({
        'method': "microsynth.microsynth.purchasing.create_po_from_open_mr",
        'args': {
            'filters': filters
        },
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
            {fieldtype:'Data', label: __('Supplier Part Number'), fieldname:'supplier_part_no'},
            {fieldtype:'Section Break'},
            {fieldtype:'HTML', fieldname:'results'}
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
            // Show confirmation dialog with qty, schedule_date, company
            open_confirmation_dialog(selected, report);
        }
    });
    dialog.show();

    // Force wider dialog
    setTimeout(() => {
        let modals = document.getElementsByClassName('modal-dialog');
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = '1200px';
        }
    }, 300);

    const f = dialog.fields_dict;
    dialog.selected_item = null;

    // Clear filters button
    f.clear_filters.$input.addClass('btn-secondary');
    f.clear_filters.$input.on('click', () => {
        ['item_name_part','material_code','supplier_name','supplier_part_no'].forEach(fn => {
            f[fn].set_value('');
        });
        f.results.$wrapper.html('<div class="text-muted">' + __('Set at least one filter to see results.') + '</div>');
        dialog.selected_item = null;
    });

    function update_list() {
        // check if any filter set
        const filters_set = ['item_name_part','material_code','supplier_name','supplier_part_no'].some(fn => f[fn].get_value());
        if (!filters_set) {
            f.results.$wrapper.html('<div class="text-muted">' + __('Set at least one filter to see results.') + '</div>');
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
                if (items.length === 0) {
                    // No results but filters set -> show "Request Item" button
                    f.results.$wrapper.html(`
                        <div class="alert alert-info">
                            ${__('No matching items found.')}
                            <br><button class="btn btn-primary" id="request-item-btn">${__('Request Item')}</button>
                        </div>
                    `);

                    f.results.$wrapper.find('#request-item-btn').on('click', () => {
                        dialog.hide();
                        open_item_request_dialog(report);
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
                                <th>${__('Material Code')}</th>
                                <th>${__('Supplier')}</th>
                                <th>${__('Supplier Name')}</th>
                                <th>${__('Supplier Part No')}</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                items.forEach(it => {
                    html += `
                        <tr>
                            <td><input type="radio" name="select_item" value="${it.name}"></td>
                            <td>${frappe.utils.escape_html(it.name)}</td>
                            <td>${frappe.utils.escape_html(it.item_name || '')}</td>
                            <td>${frappe.utils.escape_html(it.material_code || '')}</td>
                            <td>${frappe.utils.escape_html(it.supplier || '')}</td>
                            <td>${frappe.utils.escape_html(it.supplier_name || '')}</td>
                            <td>${frappe.utils.escape_html(it.supplier_part_no || '')}</td>
                        </tr>
                    `;
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


// Confirmation dialog after selecting an item
function open_confirmation_dialog(selected, report) {
    const today = frappe.datetime.nowdate();

    let d = new frappe.ui.Dialog({
        'title': __('Confirm Material Request'),
        'fields': [
            { fieldtype: 'Data', label: __('Item Name'), fieldname: 'item_name', read_only: 1, default: selected.item_name },

            { fieldtype: 'Section Break' },

            { fieldtype: 'Data', label: __('Item Code'), fieldname: 'item_code', read_only: 1, default: selected.name },
            { fieldtype: 'Data', label: __('Supplier'), fieldname: 'supplier', read_only: 1, default: selected.supplier },
            { fieldtype: 'Int', label: __('Quantity'), fieldname: 'qty', reqd: true, default: 1, min: 1 },
            { fieldtype: 'Date', label: __('Required By'), fieldname: 'schedule_date', reqd: true },

            { fieldtype: 'Column Break' },

            { fieldtype: 'Data', label: __('Supplier Part No'), fieldname: 'supplier_part_no', read_only: 1, default: selected.supplier_part_no },
            { fieldtype: 'Data', label: __('Supplier Name'), fieldname: 'supplier_name', read_only: 1, default: selected.supplier_name },
            { fieldtype: 'Data', label: __('Material Code'), fieldname: 'material_code', read_only: 1, default: selected.material_code },
            { fieldtype: 'Link', label: __('Company'), fieldname: 'company', reqd: true, options: 'Company', default: frappe.defaults.get_default('company') }
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
                    'company': values.company
                },
                callback(r) {
                    if (!r.exc && r.message) {
                        const link = `<a href="/desk#Form/Material Request/${r.message}" target="_blank">${r.message}</a>`;
                        frappe.msgprint({
                            'title': __('Success'),
                            'indicator': 'green',
                            'message': __('Material Request created and submitted: {0}', [link])
                        });
                        d.hide();
                        report.refresh();
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


function open_item_request_dialog(report) {
    let d = new frappe.ui.Dialog({
        'title': __('New Item Request'),
        'fields': [
            // Left column
            {fieldtype:'Data', label: __('Item Name'), fieldname:'item_name', reqd:true},
            {fieldtype:'Link', label: __('Supplier'), fieldname:'supplier', options: 'Supplier'},
            {fieldtype:'Float', label: __('Quantity'), fieldname:'qty', reqd:true, default:1, min: 0.0001},
            {fieldtype:'Currency', label: __('Rate'), fieldname:'rate'},
            {fieldtype:'Link', label: __('Company'), fieldname:'company', options: 'Company', reqd:true, default: frappe.defaults.get_default('company')},

            {fieldtype:'Column Break'},

            // Right column
            {fieldtype:'Data', label: __('Supplier Item Code'), fieldname:'supplier_part_no'},
            {fieldtype:'Data', label: __('Supplier Name'), fieldname:'supplier_name', reqd:true},
            {fieldtype:'Link', label: __('UOM (unit of measure)'), fieldname:'uom', options: 'UOM', default: 'Pcs'},
            {fieldtype:'Link', label: __('Currency'), fieldname:'currency', options: 'Currency'},
            {fieldtype:'Date', label: __('Required By'), fieldname:'schedule_date'},

            {fieldtype:'Section Break'},

            // Full width comments
            {fieldtype:'Text', label: __('Comments'), fieldname:'comment', colspan: 2}
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
    // TODO: Fetch Supplier Name if Supplier is set but not Supplier Name
}
