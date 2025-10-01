/* Custom script extension for Material Request */
frappe.ui.form.on('Material Request', {
    onload(frm) {
        // remove empty row from items table
        if (frm.doc.__islocal && frm.doc.items && frm.doc.items.length === 1 && !frm.doc.items[0].item_code) {
            frm.clear_table('items');
            frm.refresh_field('items');
        }
    },
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }

        setTimeout(function () {
            cur_frm.fields_dict.items.grid.get_field('item_code').get_query =
                function(frm, dt, dn) {
                    return {
                        query: "microsynth.microsynth.filters.find_purchasing_items",
                        filters: {
                            "item_group": 'Purchasing',
                            "disabled": 0
                        }
                    };
                };
        }, 1000);

        hide_in_words();
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }
    },
    add_item(frm) {
        // Call the dialog
        select_item(frm);
      }
});


function select_item(frm) {
    let dialog = new frappe.ui.Dialog({
        'title': __('Select Purchasing Item'),
        'fields': [
            {
                'fieldtype': 'Data',
                'label': __('Item Name'),
                'fieldname': 'item_name_part'
            },
            {
                'fieldtype': 'Data',
                'label': __('Material Code'),
                'fieldname': 'material_code'
            },
            {
                'fieldtype': 'Button',
                'label': __('Clear Filters'),
                'fieldname': 'clear_filters'
            },
            {
                'fieldtype': 'Column Break'
            },
            {
                'fieldtype': 'Data',
                'label': __('Supplier Name'),
                'fieldname': 'supplier_name'
            },
            {
                'fieldtype': 'Data',
                'label': __('Supplier Part Number'),
                'fieldname': 'supplier_part_no'
            },
            {
                'fieldtype': 'Section Break'
            },
            {
                'fieldtype': 'HTML',
                'fieldname': 'results'
            }
        ],
        'primary_action_label': __('Select'),
        'primary_action'(values) {
            const selected = dialog.selected_item;
            if (!selected) {
                if (document.activeElement.getAttribute('data-fieldtype') !== 'Data') {
                    frappe.msgprint(__('Please select an Item'));
                }
                update_list();
                return;
            }

            const row = frm.add_child('items');
            row.item_code = selected.name;

            frappe.db.get_doc('Item', selected.name).then(item => {
                row.item_name = item.item_name;
                row.description = item.description;
                row.uom = item.stock_uom;
                row.qty = 1;
                row.conversion_factor = 1;
                //row.schedule_date = frappe.datetime.nowdate();
                frm.refresh_field('items');
                dialog.hide();
            });
        }
    });

    dialog.show();

    // Force wider dialog
    setTimeout(function () {
        const modals = document.getElementsByClassName('modal-dialog');
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = '1200px';
        }
    }, 300);

    const f = dialog.fields_dict;
    dialog.selected_item = null;

    // Function to update the list of items based on filter values
    function update_list() {
        // Check if any filter is set (returns true if at least one has a value)
        const filters_set = ['item_name_part', 'material_code', 'supplier_name', 'supplier_part_no']
            .some(key => f[key] && f[key].get_value());

        // If no filters are set, show a message and exit early
        if (!filters_set) {
            f.results.$wrapper.html('<div class="text-muted">' + __('Set at least one filter to see results.') + '</div>');
            return;
        }

        // Call backend method to fetch filtered items
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.get_purchasing_items',
            'args': {
                'item_name_part': f.item_name_part.get_value(),
                'material_code': f.material_code.get_value(),
                'supplier_name': f.supplier_name.get_value(),
                'supplier_part_no': f.supplier_part_no.get_value()
            },
            'callback'(r) {
                const items = r.message || [];

                // Build HTML table to display matching items
                let html = `
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>${__('Select')}</th>
                                <th>${__('Item')}</th>
                                <th>${__('Item Name')}</th>
                                <th>${__('Material Code')}</th>
                                <th>${__('Supplier')}</th>
                                <th>${__('Supplier Name')}</th>
                                <th>${__('Supplier Item Code')}</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                // Add one row per matching item
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

                // Inject the built HTML into the dialog
                f.results.$wrapper.html(html);

                // Save the selected item (on radio button change)
                f.results.$wrapper.find('input[type=radio][name=select_item]').on('change', function () {
                    dialog.selected_item = items.find(i => i.name === $(this).val());
                });
            }
        });
    }

    // Attach change event listeners to filter fields
    ['item_name_part', 'material_code', 'supplier_name', 'supplier_part_no'].forEach(fieldname => {
        if (f[fieldname]) {
            f[fieldname].$input.on('change', update_list); // Refresh list on input change
        }
    });

    // Style and attach handler for "Clear Filters" button
    f.clear_filters.$input.addClass('btn-secondary');
    f.clear_filters.$input.on('click', () => {
        // Clear all filter values
        ['item_name_part', 'material_code', 'supplier_name', 'supplier_part_no'].forEach(fieldname => {
            f[fieldname].set_value('');
        });

        // Show placeholder message in results area
        f.results.$wrapper.html('<div class="text-muted">' + __('Set at least one filter to see results.') + '</div>');

        // Reset selected item
        dialog.selected_item = null;
    });

    // Trigger initial list load (if filters are preset)
    update_list();
}
