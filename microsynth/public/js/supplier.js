/* Custom script extension for Supplier */


frappe.ui.form.on('Supplier', {
    refresh(frm) {
        cur_frm.fields_dict['default_item'].get_query = function() {
            return {
                filters: {
                    'is_purchase_item': 1,
                    'disabled': 0
                }
            };
        };

        frm.set_query('default_tax_template', 'accounts', function(doc, cdt, cdn) {
            var d = locals[cdt][cdn];
            var filters = {
                'company': d.company
            }
            return {'filters': filters}
        });

    }
});
