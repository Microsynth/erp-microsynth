// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Document', {
    refresh: function(frm) {
        // reset overview html
        cur_frm.set_df_property('overview', 'options', null);
        
        // prepare attachment watcher (to get events/refresh when an attachment is removed or added)
        setup_attachment_watcher(frm);
        
        // fresh document: add creation tags
        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
            cur_frm.set_df_property('title', 'read_only', false);       // allow to set title for a fresh document
        }
        
        // allow to set title in specific conditions
        if (["In Review", "Reviewed"].includes(frm.doc.status)) {
            cur_frm.set_df_property('title', 'read_only', false);
        }
        
        // allow review when document is on draft with an attachment
        if ((!frm.doc.__islocal) && ((cur_frm.attachments) && (cur_frm.attachments.get_attachments().length > 0)))  {
            frm.add_custom_button(__("Review request"), function() {
                request_review(frm);
            });
        }
        // allow to create new versions from valid documents
        if (frm.doc.docstatus > 0) {
            frm.add_custom_button(__("New version"), function() {
                create_new_version(frm);
            });
        }
        
        // sign & release control
        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();
        }
        if ((!frm.doc.__islocal)
            && (frm.doc.docstatus === 1) 
            && (frm.doc.reviewed_on) 
            && (frm.doc.reviewed_by)
            && (!frm.doc.released_on)
            && (!frm.doc.released_by)
            && ((cur_frm.attachments) && (cur_frm.attachments.get_attachments().length > 0))) {
            // add release button
            cur_frm.page.set_primary_action(
                __("Release"),
                function() {
                    release();
                }
            );
        }
        
        // Training request
        if (((cur_frm.attachments) && (cur_frm.attachments.get_attachments().length > 0))
            && ["Released", "Valid" ].includes(frm.doc.status)
            && (frm.doc.released_on)
            && (frm.doc.released_by))  {
            frm.add_custom_button(__("Training request"), function() {
                request_training(frm);
            });
        }

        // access protection: only owner and system manager can remove attachments
        if ((["Released", "Valid", "Invalid"].includes(frm.doc.status)) || ((frappe.session.user !== frm.doc.owner) && (!frappe.user.has_role("System Manager")))) {
            access_protection();
        }
        
        // attachment monitoring: if the review is available but no attachment -> drop review because attachment has been removed
        if ((frm.doc.reviewed_on) && ((cur_frm.attachments) && (cur_frm.attachments.get_attachments().length === 0))) {
            cur_frm.set_value("reviewed_on", null);
            cur_frm.set_value("reviewed_by", null);
            cur_frm.set_value("status", "In Review");
            cur_frm.save_or_update();
            frappe.msgprint( __("Warning: the review has been cleared because the attachment was removed. Please add an attachment and requerst a new review."), __("Validation") ); 
        }
        
        // fetch document overview
        if (!frm.doc.__islocal) {
            frappe.call({
                'method': 'get_overview',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('overview', 'options', r.message);
                }
            });
        }
    }
});


function request_review() {
    frappe.prompt([
        {'fieldname': 'reviewer', 'fieldtype': 'Link', 'label': __('Reviewer'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1}
    ],
    function(values){
        console.log(values.reviewer);
        if (values.reviewer === cur_frm.doc.created_by) {
            frappe.msgprint( __("Please select a different reviewer than the creator."), __("Validation") );
        } else {
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_review.qm_review.create_review',
                'args': {
                    'reviewer': values.reviewer,
                    'dt': cur_frm.doc.doctype,
                    'dn': cur_frm.doc.name,
                    'due_date': values.due_date
                },
                "callback": function(response) {
                    console.log("created review request...")
                    cur_frm.reload_doc();
                }
            });
        }
    },
    __('Please choose a reviewer'),
    __('Request review')
    )
}


function create_new_version(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_document.qm_document.create_new_version',
        'args': {
            'doc': frm.doc.name
        },
        'callback': function (r) {
            frappe.set_route("Form", "QM Document", r.message.name);
        }
    });
}


function release() {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_document.qm_document.set_released',
        'args': {
            'doc': cur_frm.doc.name,
            'user': frappe.session.user
        }
    });

    frappe.prompt([
            {'fieldname': 'password', 'fieldtype': 'Password', 'label': __('Approval Password'), 'reqd': 1}  
        ],
        function(values){
            // check password and if correct, submit
            frappe.call({
                'method': 'microsynth.qms.signing.sign',
                'args': {
                    'dt': "QM Document",
                    'dn': cur_frm.doc.name,
                    'user': frappe.session.user,
                    'password': values.password
                },
                "callback": function(response) {
                    cur_frm.reload_doc();
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}

function request_training() {
    frappe.prompt([
        {'fieldname': 'trainees', 
         'fieldtype': 'Table',
         'label': 'Trainees',
         'reqd': 1,
         'fields': [ 
            {'fieldname': 'trainee', 
             'fieldtype': 'Link', 
             'label': __('Trainee'), 
             'options':'User', 
             'in_list_view': 1,
             'reqd': 1} ],

         'data': [],
         'get_data': () => { return [];}
        },
        { 'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1 }
    ],
    function(values){
        console.log(values.trainees)
        for (var i = 0; i < values.trainees.length; i++)  {
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_training_record.qm_training_record.create_training_record',
                           
                'args': {
                    'trainee': values.trainees[i].trainee,
                    'dt': cur_frm.doc.doctype,
                    'dn': cur_frm.doc.name,
                    'due_date': values.due_date
                },
                "callback": function(response) {
                    console.log("created training record request for " + values.trainee[i].trainee)
                }
            })
        }



    },
    __('Please choose a trainee'),
    __('Request training')
    )
}

function setup_attachment_watcher(frm) {
    // if (!locals.attachment_node) {
        setTimeout(function () {
            // Select the node that will be observed for mutations
            const targetNodes = document.getElementsByClassName("form-attachments");
            if (targetNodes.length > 0) {
                const targetNode = targetNodes[0];
                
                // Options for the observer (which mutations to observe)
                const config = { attributes: true, childList: true, subtree: true };
                
                // Callback function to execute when mutations are observed
                const callback = (mutationList, observer) => {
                    for (const mutation of mutationList) {
                        if (mutation.type === "childList") {
                            console.log("An attachment added or removed.");
                            cur_frm.reload_doc();
                        }
                    }
                };

                // Create an observer instance linked to the callback function
                const observer = new MutationObserver(callback);

                // Start observing the target node for configured mutations
                observer.observe(targetNode, config);
                
                locals.attachment_node = targetNode;
            } else {
                console.log("no node found!!!!");
            }
            
            // change the upload callback action
            /*cur_frm.attachments.attachment_uploaded = function() {
                cur_frm.reload_doc();
            }*/
            
        }, 1000);
    //}
}
