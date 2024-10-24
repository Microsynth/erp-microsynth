// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Settings', {
    refresh: function(frm) {
        cur_frm.add_custom_button(
            __("Request SOP Training"),
            function() {
                request_sop_training(frm);
            }
        );
    }
});

function create_training_request(qm_document, user_name, due_date) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_training_record.qm_training_record.create_training_record',
        'args': {
            'trainee': user_name,
            'dt': 'QM Document',
            'dn': qm_document,
            'due_date': due_date
        }
    })
}

function request_sop_training(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_document.qm_document.get_valid_sops',
        'args': {
            'qm_process_assignments': frm.doc.qm_process_assignments
        },
        'callback': function(response) {
            var valid_sops = response.message;
            frappe.prompt([
                {'fieldname': 'qm_documents', 
                 'fieldtype': 'Table',
                 'label': 'QM Documents',
                 'reqd': 1,
                 'fields': [ 
                    {
                        'fieldname': 'name',
                        'fieldtype': 'Link',
                        'label': 'QM Document',
                        'options': 'QM Document',
                        'in_list_view': 1,
                        'reqd': 1,
                        'columns': 3  // increase the width of this column (total should be < 11)
                    },
                    {
                        'fieldname': 'title',
                        'fieldtype': 'Data',
                        'label': 'Title',
                        'in_list_view': 1,
                        'reqd': 1
                    }
                 ],
                 'data': valid_sops,
                 'get_data': () => { return valid_sops;}
                },
                { 'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1 }
            ],
            function(values){
                for (var i = 0; i < values.qm_documents.length; i++) {
                    create_training_request(values.qm_documents[i].name, cur_frm.doc.name, values.due_date);
                }
            },
            __('Add or delete SOPs if necessary'),
            __('Request training')
            );
        }
    })
}
