// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

const document_types_with_review = ['SOP', 'FLOW', 'QMH'];


frappe.ui.form.on('QM Document', {
    refresh: function(frm) {
        // fresh document: add creation tags
        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
            // on fresh documents, hide company field (will be clean on insert to prevent default)
            cur_frm.set_df_property('company', 'hidden', true);
            // ensure that a fresh document is always created in draft status
            cur_frm.set_value("status", "Draft");
        }

        // company reset-controller
        if (frm.doc.__islocal) {
            // set flag that this is a new document
            locals.initial_save = true;
        } else {
            if (locals.initial_save) {
                // this is the first refresh after the initial save: reset flag and reload to load company from DB
                locals.initial_save = false;
                cur_frm.set_value("company", null);
            }
        }

        // reset overview html
        cur_frm.set_df_property('overview', 'options', '<p><span class="text-muted">No data for overview available.</span></p>');

        // check if document requires review
        var requires_review = document_types_with_review.includes(frm.doc.document_type);

        // set information bar for missing file
        cur_frm.dashboard.clear_comment();
        if (!frm.doc.__islocal
            && ((!cur_frm.attachments)
                || (!cur_frm.attachments.get_attachments())
                || (cur_frm.attachments && (cur_frm.attachments.get_attachments().length === 0)))) {
                if (['SOP', 'APPX', 'FLOW', 'QMH'].includes(frm.doc.document_type)) {
                    cur_frm.dashboard.add_comment( __("Please attach a PDF and a document."), 'red', true);
                } else {
                    cur_frm.dashboard.add_comment( __("Please attach a document."), 'red', true);
                }
        }

        // prepare attachment watcher (to get events/refresh when an attachment is removed or added)
        setup_attachment_watcher(frm);

        const isQAU = frappe.user.has_role('QAU');
        const isInvalid = frm.doc.status === 'Invalid';
        const isNew = frm.doc.__islocal;

        // only allow QAU to set/change field "Registered Externally" but not in status Invalid
        frm.set_df_property('registered_externally', 'read_only', !(isQAU && !isInvalid));
        // ensure write access to Process and Chapter before the first save
        frm.set_df_property('qm_process', 'read_only', !(isQAU || isNew));
        frm.set_df_property('chapter', 'read_only', !(isQAU || isNew));

        // Only creator and QAU can change these fields in Draft status: Title, Company, Classification Level, linked Documents
        if (!(["Draft"].includes(frm.doc.status) && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) && !frm.doc.__islocal) {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('classification_level', 'read_only', true);
            cur_frm.set_df_property('valid_from', 'read_only', true);
            cur_frm.set_df_property('valid_till', 'read_only', true);
        }

        // when a document is valid or invalid, the valid_from field must be read-only
        if (["Valid", "Invalid"].includes(frm.doc.status) && !frm.doc.__islocal) {
            cur_frm.set_df_property('valid_from', 'read_only', true);
        } else {
            if (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU') || (frm.doc.reviewed_by && frappe.session.user === frm.doc.reviewed_by)) {
                cur_frm.set_df_property('valid_from', 'read_only', false);
            }
        }

        // when a document is invalid, the fields valid_till and the table linked_documents must be read-only
        if (["Invalid"].includes(frm.doc.status)) {
            cur_frm.set_df_property('valid_till', 'read_only', true);
            cur_frm.set_df_property('linked_documents', 'read_only', true);
            // Add button to search valid version
            cur_frm.dashboard.add_comment( __("<b>Invalid</b> document: Do <b>not</b> use the attachments anymore!"), 'red', true);
            frm.add_custom_button(__("Search valid version"), function() {
                frappe.set_route("List", "QM Document", {"name": cur_frm.doc.name.split("-")[0], "status": "Valid"});
            }).addClass("btn-primary");
        } else {
            if (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU')) {
                cur_frm.set_df_property('valid_till', 'read_only', false);
            }
            if (frappe.user.has_role('QAU')) {
                cur_frm.set_df_property('linked_documents', 'read_only', false);
            }
        }

        // update QM Document.status if valid_from <= today and status is Released
        if (frm.doc.valid_from && ["Released"].includes(frm.doc.status)) {
            if (frm.doc.valid_from <= frappe.datetime.get_today()) {
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

        // allow revision when document is valid
        if ((["Valid"].includes(frm.doc.status)) && !frm.doc.__islocal) {
            frm.add_custom_button(__("Revision request"), function() {
                request_revision(frm);
            }).addClass("btn-primary");
        }

        // Allow QAU to invalidate
        if (["Created", "Released", "Valid"].includes(frm.doc.status) && frappe.user.has_role('QAU') && !frm.doc.__islocal) {
            frm.add_custom_button(__("Invalidate"), function() {
                invalidate(frm);
            }).addClass("btn-danger");
        }

        // allow to create new versions from valid documents
        if (frm.doc.docstatus > 0) {
            frm.add_custom_button(__("Create new version"), function() {
                create_new_version(frm);
            });
        }

        // sign & release control
        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();

            // prevent document type changes after the document number has been assigned
            cur_frm.set_df_property('document_type', 'read_only', true);
            //cur_frm.set_df_property('qm_process', 'read_only', true);
            //cur_frm.set_df_property('chapter', 'read_only', true);
        }

        // allow the creator to sign a document (after pingpong review)
        if ((!frm.doc.__islocal)
            && (["Draft"].includes(frm.doc.status))
            && (frappe.session.user === frm.doc.created_by)
            && (!frm.doc.released_on)
            && (!frm.doc.released_by)
            && ((cur_frm.attachments)
                && (cur_frm.attachments.get_attachments())
                && (cur_frm.attachments.get_attachments().length > 0)
                && (["LIST", "FORM", "CL"].includes(frm.doc.document_type)
                    || (cur_frm.attachments.get_attachments().length > 1
                        && has_pdf(cur_frm.attachments.get_attachments()))))
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
                    && (frm.doc.reviewed_by)
                    && (frappe.session.user != frm.doc.reviewed_by)))) {  // releaser needs to be different from reviewer
            if (requires_review || frappe.session.user != frm.doc.created_by) {  // releaser needs to be different from creator if no review is required
                // add release button
                cur_frm.page.set_primary_action(
                    __("Release"),
                    function() {
                        release();
                    }
                );
            }
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
                'method': 'microsynth.qms.doctype.qm_document.qm_document.get_overview_wrapper',
                'args': {
                    'doc_name': frm.doc.name
                },
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

            // disable dropping things
            window.addEventListener("drop", stop_drop, true);
        } else {
            // enable dropping things (i.e. revert prevention from submitted document)
            window.removeEventListener("drop", stop_drop, true);
        }

        // only allow creator and QAU to set/change valid till date
        if ((frm.doc.docstatus == 1)
            && !((frappe.session.user === frm.doc.created_by)
                  || (frappe.user.has_role("QAU")))) {
            cur_frm.set_df_property('valid_till', 'read_only', true);
        }

        /* Linked Documents filter: only show Valid QM Documents */
        frm.fields_dict.linked_documents.grid.get_field('qm_document').get_query = function() {
            return {
                    filters: [
                        ["status", "=", "Valid"]
                ]
            };
        };

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();

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
    },
    qm_process: function(frm) {
        if (frm.doc.__islocal) {
            fetch_chapter(frm);
        }
    },
    valid_from: function(frm) {
        if (frm.doc.valid_from < frappe.datetime.get_today()) {
            cur_frm.set_value("valid_from", frappe.datetime.get_today());
            frappe.msgprint( __("Valid from date is not allowed to be in the past. The Valid from date was set to today."), __("Validation") );
        }
        if ((frm.doc.valid_from) && (frm.doc.valid_till) && (frm.doc.valid_till < frm.doc.valid_from)) {
            cur_frm.set_value("valid_from", null);
            frappe.msgprint( __("Valid from date cannot be after the valid till date."), __("Validation") );
        }
    },
    valid_till: function(frm) {
        if (frm.doc.valid_till < frappe.datetime.get_today()) {
            cur_frm.set_value("valid_till", null);
            frappe.msgprint( __("Valid till date is not allowed to be in the past. Please set the Valid till date to today or to the future."), __("Validation") );
        }
        if ((frm.doc.valid_from) && (frm.doc.valid_till) && (frm.doc.valid_till < frm.doc.valid_from)) {
            cur_frm.set_value("valid_till", null);
            frappe.msgprint( __("Valid till date cannot be before the valid from date."), __("Validation") );
        }
    }
});


function fetch_chapter(frm) {
    frappe.call({
        'method': 'frappe.client.get',
        'args': {
            'doctype': "QM Process",
            'name': frm.doc.qm_process
        },
        'callback': function (r) {
            var qm_process = r.message;
            cur_frm.set_value("chapter", qm_process.chapter);
            if (qm_process.chapter > 0) {
                cur_frm.set_df_property('chapter', 'read_only', true);
            } else {
                cur_frm.set_df_property('chapter', 'read_only', false);
            }
        }
    });
}


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
                    cur_frm.reload_doc();
                }
            });
        }
    },
    __('Please choose a reviewer'),
    __('Request review')
    )
}


function request_revision() {
    frappe.prompt([
        {'fieldname': 'revisor', 'fieldtype': 'Link', 'label': __('Revisor'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_revision.qm_revision.create_revision',
            'args': {
                'revisor': values.revisor,
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'due_date': values.due_date
            },
            "callback": function(response) {
                cur_frm.reload_doc();
            }
        });
    },
    __('Please choose a revisor'),
    __('Request revision')
    )
}


function invalidate(frm) {
    let additional_warning = "";
    if (frm.doc.status == "Valid") {
        additional_warning = "<br>There will be <b>no other valid version.</b>";
    }
    frappe.confirm("Are you sure you want to set this QM Document '" + frm.doc.name + "' <b>irreversibly</b> to the status <b>Invalid</b>?" + additional_warning,
    () => {
        // on yes
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_document.qm_document.invalidate_document',
            'args': {
                'qm_document': cur_frm.doc.name
            },
            'callback': function(response) {
                cur_frm.reload_doc();
                frappe.show_alert( __("Status changed to Invalid.") );
            }
        });
    }, () => {
        frappe.show_alert('No changes');
    });
}


function create_new_version(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_document.qm_document.create_new_version',
        'args': {
            'doc': frm.doc.name,
            'user': frappe.session.user
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
            // set the created_on date to the current date
            cur_frm.set_value("created_on", frappe.datetime.get_today());
            cur_frm.save().then(function() {
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
                            // set creation date and user and set status to "Created" (if password was correct)
                            frappe.call({
                                'method': 'microsynth.qms.doctype.qm_document.qm_document.set_created',
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
                'method': 'microsynth.qms.doctype.qm_document.qm_document.invalidate_document',
                'args': {
                    'qm_document': cur_frm.doc.name
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
    var filtered_trainees = []
    for (var i = 0; i < trainees.length; i++) {
        // Creator, Reviewer and Releaser do not need to get trained
        if (![cur_frm.doc.created_by, cur_frm.doc.reviewed_by, cur_frm.doc.released_by].includes(trainees[i].user_name)) {
            filtered_trainees.push(trainees[i]);
        }
    }
    frappe.prompt([
        {'fieldname': 'trainees',
         'fieldtype': 'Table',
         'label': 'Trainees',
         'reqd': 1,
         'fields': [
            {'fieldname': 'user_name',
             'fieldtype': 'Link',
             'label': 'Trainee',
             'options': 'Signature',
             'in_list_view': 1,
             'reqd': 1,
             'get_query': function() { return { filters: {'name': ['LIKE', '%@microsynth%'] } } }
            }
          ],

         'data': filtered_trainees,
         'get_data': () => { return trainees;}
        },
        { 'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1 }
    ],
    function(values){
        for (var i = 0; i < values.trainees.length; i++) {
            create_training_request(values.trainees[i].user_name, values.due_date);
        }
    },
    __('Add or delete Trainees if necessary'),
    __('Request training')
    );
}


function request_training() {
    // Ask for Companies and QM Processes
    frappe.prompt([
        {'fieldname': 'companies',
         'fieldtype': 'Table',
         'label': 'Companies',
         'fields': [
            {'fieldname': 'company',
             'fieldtype': 'Link',
             'label': 'Company',
             'options': 'Company',
             'in_list_view': 1,
             'reqd': 1}
            ],
         'data': [{"company": cur_frm.doc.company}],
         'get_data': () => { return []; }
        },
        {'fieldname': 'qm_processes',
         'fieldtype': 'Table',
         'label': 'QM Processes',
         'fields': [
            {'fieldname': 'qm_process',
             'fieldtype': 'Link',
             'label': 'QM Process',
             'options': 'QM Process',
             'in_list_view': 1,
             'reqd': 1}
            ],
         'data': [{"qm_process": cur_frm.doc.qm_process}],
         'get_data': () => { return []; }
        }
    ],
    function(values){
        if (!values.qm_processes && !values.companies) {
            // no process and no company -> shortcut and show Request training prompt with an empty list of trainees
            request_training_prompt([]);
            return;
        }
        const qm_processes_list = [];
        if (values.qm_processes) {
            for (var i = 0; i < values.qm_processes.length; i++)  {
                qm_processes_list[i] = values.qm_processes[i].qm_process;
            }
        }
        const companies_list = [];
        if (values.companies) {
            for (var i = 0; i < values.companies.length; i++)  {
                companies_list[i] = values.companies[i].company;
            }
        }
        frappe.call({
            'method': 'microsynth.qms.report.users_by_process.users_by_process.get_users',
            'args': {
                'qm_processes': qm_processes_list,
                'companies': companies_list
            },
            'callback': function(response) {
                request_training_prompt(response.message);
            }
        })
    },
    __('Select at least one Company or QM Process'),
    __('Continue')
    );
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
                            if (cur_frm.is_dirty()) {
                                cur_frm.save();
                            }
                            else {
                                cur_frm.reload_doc();
                            }
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
            cur_frm.save_or_update();
            // notify the new creator
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_document.qm_document.notify_new_creator',
                'args': {
                    'qm_document': cur_frm.doc.name,
                    'new_creator': values.new_creator
                },
                'callback': function(response) {
                    cur_frm.reload_doc();
                }
            });
        },
        __('Set new creator'),
        __('Set')
    );
}


function has_pdf(attachments) {
    let pdfs = 0;
    for (var i = 0; i < attachments.length; i++) {
        let file_name_lowered = attachments[i].file_name.toLowerCase();
        if (file_name_lowered.endsWith(".pdf")) {
            pdfs += 1;
        }
    }
    return pdfs == 1;
}
