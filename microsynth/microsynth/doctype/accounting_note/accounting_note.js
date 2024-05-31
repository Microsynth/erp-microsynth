// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Accounting Note', {
    refresh: function(frm) {
        // restrict options of doctypes
        frm.fields_dict.reference_doctype.get_query = function(doc) {
            return {
                'filters': [
                    ['name', 'IN', ['Purchase Invoice', 'Sales Invoice', 'Payment Entry', 'Journal Entry']]
                ]
            }
        }
        frm.fields_dict.related_documents.grid.get_field('reference_doctype').get_query = function(doc, cdt, cdn) {
            return {
                'filters': [
                    ['name', 'IN', ['Purchase Invoice', 'Sales Invoice', 'Payment Entry', 'Journal Entry']]
                ]
            }
        }
    }
});

