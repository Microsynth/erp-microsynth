// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Batch Invoice Processing Settings', {
    refresh: function(frm) {
        frm.fields_dict.company_settings.grid.get_field('default_tax').get_query =   
            function(frm, dt, dn) {   
                var v = locals[dt][dn];
                return {
                    'filters': {
                        "company": v.company
                    }
                }
            }; 
    }
});
