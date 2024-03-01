// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

const document_types_with_review = ['SOP', 'FLOW', 'QMH', 'APPX'];


frappe.ui.form.on('QM Document', {
    refresh: function(frm) {
        // reset overview html
        cur_frm.set_df_property('overview', 'options', '<p><span class="text-muted">No data for overview available.</span></p>');

        // check if document requires review
        var requires_review = document_types_with_review.includes(frm.doc.document_type);
        
        // set information bar for missing file
        cur_frm.dashboard.clear_comment();
        if ((!cur_frm.attachments) 
            || (!cur_frm.attachments.get_attachments())
            || ((cur_frm.attachments) && (cur_frm.attachments.get_attachments().length === 0))) {
                cur_frm.dashboard.add_comment( __("Please attach a document."), 'red', true);
        }

        // prepare attachment watcher (to get events/refresh when an attachment is removed or added)
        setup_attachment_watcher(frm);

        // set valid_from to read_only if it is set, not in the future and QM Document is not a Draft
        if (frm.doc.valid_from && frm.doc.docstatus > 0) {
            var valid_from_date = (new Date(frm.doc.valid_from)).setHours(0,0,0,0);
            var today = (new Date()).setHours(0,0,0,0);  // call setHours to take the time out
            if (valid_from_date <= today) {
                cur_frm.set_df_property('valid_from', 'read_only', true);
            }
        }

        // fresh document: add creation tags
        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
            // on fresh documents, hide company field (will be clean on insert to prevent default)
            cur_frm.set_df_property('company', 'hidden', true);
        }

        // update QM Document.status if valid_from <= today and status is Released
        if (frm.doc.valid_from && ["Released"].includes(frm.doc.status)) {
            var valid_from_date = (new Date(frm.doc.valid_from)).setHours(0,0,0,0);
            var today = (new Date()).setHours(0,0,0,0);  // call setHours to take the time out
            if (valid_from_date <= today) {
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_document.qm_document.set_valid_document',
                    'args': {
                        'qm_docname': cur_frm.doc.name
                    },
                    "callback": function(response) {
                        //cur_frm.reload_doc();
                        if (response.message) {
                            cur_frm.reload_doc();
                            frappe.show_alert( __("Status changed to Valid.") );
                        }                        
                    }
                });
            } 
        }
        
        // allow review when document is on created with an attachment
        if ((["Created"].includes(frm.doc.status))
            && (!frm.doc.reviewed_on) 
            && (!frm.doc.reviewed_by)
            && ((cur_frm.attachments)
            && (cur_frm.attachments.get_attachments())
            && (cur_frm.attachments.get_attachments().length > 0))
            && (requires_review)) {
            frm.add_custom_button(__("Review request"), function() {
                request_review(frm);
            }).addClass("btn-primary");
        }

        // Invalidate
        if (["Valid"].includes(frm.doc.status) && frappe.user.has_role('QAU')) {
            frm.add_custom_button(__("Invalidate"), function() {
                invalidate(frm);
            }).addClass("btn-danger");
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
            
            // prevent document type changes after the document number has been assigned
            cur_frm.set_df_property('document_type', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('chapter', 'read_only', true);
        }

        // allow the creator to sign a document (after pingpong review)
        if ((!frm.doc.__islocal)
            && (["Draft"].includes(frm.doc.status))
            && (frappe.session.user === frm.doc.created_by)
            && (!frm.doc.released_on)
            && (!frm.doc.released_by)
            && ((cur_frm.attachments) 
            && (cur_frm.attachments.get_attachments())
            && (cur_frm.attachments.get_attachments().length > 0))
            ) {
            // add sign button
            cur_frm.page.set_primary_action(
                __("Sign"),
                function() {
                    sign_creation();
                }
            );
        }
        
        // allow the creator or QAU to change creator (transfer document)
        if ((!frm.doc.__islocal)
            && (["Draft"].includes(frm.doc.status))
            && ((frappe.session.user === frm.doc.created_by) || (frappe.user.has_role('QAU')))
            ) {
            // add change creator button
            cur_frm.add_custom_button(
                __("Change Creator"),
                function() {
                    change_creator();
                }
            );
        }

        // add release/reject buttons if applicable
        if ((!frm.doc.__islocal)
            && (["Created", "Reviewed"].includes(frm.doc.status))
            && (!frm.doc.released_on)
            && (!frm.doc.released_by)
            && ((cur_frm.attachments) 
            && (cur_frm.attachments.get_attachments())
            && (cur_frm.attachments.get_attachments().length > 0))
            && (frappe.user.has_role('QAU'))
            && (!requires_review                                // needs no review (short process)
                || ((frm.doc.docstatus === 1)                   // or is reviewed
                    && (["Reviewed"].includes(frm.doc.status))  // long process needs to be reviewed
                    && (frm.doc.reviewed_on) 
                    && (frm.doc.reviewed_by)))) {
            // add release button
            cur_frm.page.set_primary_action(
                __("Release"),
                function() {
                    release();
                }
            );
            // add reject button
            cur_frm.page.set_secondary_action(
                __("Reject"),
                function() {
                    reject();
                }
            );
        }

        // Training request
        if (((cur_frm.attachments) 
            && (cur_frm.attachments.get_attachments())
            && (cur_frm.attachments.get_attachments().length > 0))
            && ["Released", "Valid" ].includes(frm.doc.status)
            && (frm.doc.released_on)
            && (frm.doc.released_by))  {
            frm.add_custom_button(__("Training request"), function() {
                request_training(frm);
            });
        }

        // access protection: only owner and system manager can remove attachments
        //if ((["Released", "Valid", "Invalid"].includes(frm.doc.status)) || ((frappe.session.user !== frm.doc.owner) && (!frappe.user.has_role("System Manager")))) {
        if (!["Draft"].includes(frm.doc.status)) {
            access_protection();
        } else {
            remove_access_protection();
        }

        // attachment monitoring: if the review is available but no attachment -> drop review because attachment has been removed
        if ((frm.doc.reviewed_on) && ((cur_frm.attachments) && (cur_frm.attachments.get_attachments().length === 0))) {
            clear_review(frm);
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
            
            // assure company field is visible (after insert of a frehs document it would be still hidden)
            cur_frm.set_df_property('company', 'hidden', false);
        }
        
        // remove dashboard doc (+) buttons
        var new_btns = document.getElementsByClassName("btn-new");
        for (var i = 0; i < new_btns.length; i++) {
            new_btns[i].style.visibility = "hidden";
        }
        
        // remove attach file depending on status
        if (!["Draft"].includes(frm.doc.status)) {
            var attach_btns = document.getElementsByClassName("add-attachment");
            for (var i = 0; i < attach_btns.length; i++) {
                attach_btns[i].style.visibility = "hidden";
            }
        }
    },
    document_type: function(frm) {
        if (["PROT"].includes(frm.doc.document_type)){
            cur_frm.set_value("valid_from", frappe.datetime.get_today());
        }
        else {
            if (frm.doc.valid_from) { 
                cur_frm.set_value("valid_from", null);
                frappe.show_alert("valid from date cleared")
            }
        }
    }
});


// clear review if reviewed_on or reviewed_by is set (either both or none should be set)
function clear_review(frm) {
    if ((frm.doc.reviewed_on) || (frm.doc.reviewed_by)) {
        cur_frm.set_value("reviewed_on", null);
        cur_frm.set_value("reviewed_by", null);
        cur_frm.set_value("status", "In Review");  // TODO: Is this really the correct status? A new review does not have to be requested yet.
        cur_frm.save_or_update();
        frappe.msgprint( __("Warning: the review has been cleared because the document was changed. Please add an attachment and request a new review."), __("Validation") ); 
    }
}


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


function invalidate(frm) {
    frappe.confirm("Are you sure you want to set this QM Document '" + frm.doc.name + "' to the status <b>Invalid</b>?<br>There will be <b>no other valid version.</b>",
    () => {
        cur_frm.set_value("status", "Invalid");
        setTimeout(() => {
            cur_frm.save_or_update();
            frappe.show_alert( __("Status changed to Invalid.") );
        }, "150");
    }, () => {
        frappe.show_alert('No changes');
    });
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


function sign_creation() {
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
                    'password': values.password,
                    'target_field': 'signature'
                },
                "callback": function(response) {
                    if (response.message) {
                        // set release date and user and set status to "Released" (if password was correct)
                        frappe.call({
                            'method': 'microsynth.qms.doctype.qm_document.qm_document.update_status',
                            'args': {
                                'qm_document': cur_frm.doc.name,
                                'status': "Created"
                            },
                            'async': false
                        });
                    }
                    cur_frm.reload_doc();
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}


function release() {
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
                    'password': values.password,
                    'target_field': 'release_signature'
                },
                "callback": function(response) {
                    if (response.message) {
                        // set release date and user and set status to "Released" (if password was correct)
                        frappe.call({
                            'method': 'microsynth.qms.doctype.qm_document.qm_document.set_released',
                            'args': {
                                'doc': cur_frm.doc.name,
                                'user': frappe.session.user
                            },
                            'async': false
                        });
                    }
                    cur_frm.reload_doc();
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}


function reject() {
    frappe.confirm(
        __('Are you sure you want to reject this document? This will require a new version.'),
        function (){
            // on yes
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_document.qm_document.set_rejected',
                'args': {
                    'doc': cur_frm.doc.name
                },
                'callback': function(response) {
                    cur_frm.reload_doc();
                }
            });
        },
        function (){
            // on no: do nothing
        }
    );
}


function create_training_request(user_name, due_date) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_training_record.qm_training_record.create_training_record',
        'args': {
            'trainee': user_name,
            'dt': cur_frm.doc.doctype,
            'dn': cur_frm.doc.name,
            'due_date': due_date
        },
        "callback": function(response) {
            console.log("created training record request for " + user_name)
        }
    })
}


function request_training_prompt(trainees) {
    frappe.prompt([
        {'fieldname': 'trainees', 
         'fieldtype': 'Table',
         'label': 'Trainees',
         'reqd': 1,
         'fields': [ 
            {'fieldname': 'user_name', 
             'fieldtype': 'Link', 
             'label': __('Trainee'), 
             'options':'User', 
             'in_list_view': 1,
             'reqd': 1} ],

         'data': trainees,
         'get_data': () => { return trainees;}
        },
        { 'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1 }
    ],
    function(values){
        console.log(values.trainees)
        for (var i = 0; i < values.trainees.length; i++)  {
            create_training_request(values.trainees[i].user_name, values.due_date);
        }
    },
    __('Please choose a trainee'),
    __('Request training')
    );
}


function request_training() {
    frappe.call({
        'method': 'microsynth.qms.report.users_by_process.users_by_process.get_users',
        'args': {
            'process': cur_frm.doc.process_number,
            'subprocess': cur_frm.doc.subprocess_number, 
            'chapter': cur_frm.doc.chapter
        },
        'callback': function(response) {
            console.log(response.message)
            // var trainees =  ['rolf.suter@microsynth.ch']
            request_training_prompt(response.message);
        }
    })
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


function change_creator() {
    frappe.prompt(
        [
            {'fieldname': 'new_creator', 
             'fieldtype': 'Link',
             'label': __('New Creator'),
             'reqd': 1,
             'options': 'User'
            }
        ],
        function(values){
            cur_frm.set_value("created_by", values.new_creator);
            cur_frm.save();
        },
        __('Set new creator'),
        __('Set')
    );
}
