frappe.ui.form.on('Supplier Quotation', {
    'refresh': function(frm) {
        // wait for the core handler to attach and override it with the extended item query function
        setTimeout(function() {
            cur_frm.fields_dict.items.grid.get_field('item_code').get_query =   
                function(frm, dt, dn) {   
                    return {
                        'query': "microsynth.microsynth.queries.purchase_items"
                    }
                }; 
        }, 1000);
    }
});


