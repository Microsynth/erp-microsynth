frappe.ui.form.on('AT VAT Declaration', {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Package Export'), function() {
                // Show immediate, temporary message
                frappe.show_alert({ 'message': __('Starting background package export ...'), 'indicator': 'blue' });

                frappe.call({
                    'method': 'microsynth.microsynth.taxes.async_package_export',
                    'args': {
                        'declaration_name': frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({ message: r.message, indicator: 'green' });
                        }
                    }
                });
            });
        }
    }
});
