// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('Staff Profile', {
    setup: function(frm) {
        frm.fields_dict.competencies.grid.get_field('competency').get_query = function() {
            return {
                filters: {
                    status: 'Valid',
                    docstatus: 1
                }
            };
        };
    },

    refresh: function(frm) {
        bind_competency_instruction_grid_click(frm);
        sync_competency_instruction_buttons(frm);

        if (frm.doc.docstatus === 1 && frm.doc.status !== "To Sign") {
            frm.page.clear_primary_action();
        }

        if (frm.doc.docstatus === 1 && frm.doc.status === "Valid") {
            frm.add_custom_button(__('New Version'), function() {
                create_new_version(frm);
            }, __('Create'));
        }

        if (frm.doc.docstatus === 1 && frm.doc.status === "To Sign") {
            show_signing_banner(frm);
            add_sign_button_if_allowed(frm);
        }
    },

    before_submit: function(frm) {
        if (frm.doc.confirm_valid_staff_profile_replacement) {
            delete frm.doc.confirm_valid_staff_profile_replacement;
            return;
        }

        frappe.validated = false;

        return new Promise((resolve, reject) => {
            frappe.call({
                'method': 'microsynth.qms.doctype.staff_profile.staff_profile.has_valid_staff_profile',
                'args': {
                    'employee': frm.doc.employee,
                    'current_name': frm.doc.name
                },
                'callback': function(response) {
                    const has_valid = response.message && response.message.has_valid;
                    if (!has_valid) {
                        frappe.validated = true;
                        resolve();
                        return;
                    }

                    frappe.confirm(
                        __('A valid Staff Profile already exists for this employee. If you continue, the previous valid profile will be archived when this one becomes valid. Continue?'),
                        function() {
                            frm.doc.confirm_valid_staff_profile_replacement = 1;
                            frappe.validated = true;
                            resolve();
                        },
                        function() {
                            frappe.msgprint(__('Submission cancelled.'));
                            reject();
                        }
                    );
                }
            });
        });
    }
});


function bind_competency_instruction_grid_click(frm) {
    const grid = frm.fields_dict && frm.fields_dict.competencies && frm.fields_dict.competencies.grid;
    if (!grid) {
        return;
    }

    const $table = grid.wrapper || grid.grid_rows;
    if (!$table) {
        return;
    }

    grid.wrapper.off('click', '[data-fieldname="instruction"]');
    grid.wrapper.on('click', '[data-fieldname="instruction"]', function(event) {
        const $row = $(this).closest('.grid-row');
        const row_name = $row.attr('data-name');
        const row = row_name && grid.grid_rows_by_docname ? grid.grid_rows_by_docname[row_name] : null;
        if (!row || !row.doc) {
            return;
        }
        console.log('grid instruction click', row.doc.name);
        open_competency_instruction_dialog(frm, 'Competency Assignment', row.doc.name);
        event.preventDefault();
        event.stopPropagation();
    });
}


function open_competency_instruction_dialog(frm, cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) {
        console.warn('Competency Assignment row not found', { cdt, cdn, frm: frm && frm.doc && frm.doc.name });
        return;
    }

    frappe.call({
        method: 'microsynth.qms.doctype.competency_instruction.competency_instruction.has_submitted_instruction_for_assignment',
        args: {
            competency_assignment: row.name
        },
        callback: function(response) {
            if (response.message) {
                frappe.msgprint({
                    title: __('Instruction already exists'),
                    message: __('A submitted Competency Instruction already exists for this Competency Assignment.'),
                    indicator: 'orange'
                });
                return;
            }
            show_instruction_prompt(frm.doc.employee || '', row, frm);
        }
    });
}


function show_instruction_prompt(trainee_default, row, frm) {
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Employee',
            name: trainee_default || ''
        },
        callback: function(response) {
            const trainee_name = (response && response.message && response.message.employee_name) || '';
            frappe.prompt([
                {
                    fieldname: 'instructor',
                    fieldtype: 'Link',
                    label: __('Instructor'),
                    options: 'User',
                    reqd: 1,
                    default: frappe.session.user
                },
                {
                    fieldname: 'date',
                    fieldtype: 'Date',
                    label: __('Date'),
                    reqd: 1,
                    default: frappe.datetime.get_today()
                },
                {
                    fieldtype: 'Column Break'
                },
                {
                    fieldname: 'trainee',
                    fieldtype: 'Link',
                    label: __('Trainee'),
                    options: 'Employee',
                    reqd: 1,
                    default: trainee_default,
                    read_only: 1
                },
                {
                    fieldname: 'trainee_name',
                    fieldtype: 'Data',
                    label: __('Trainee Name'),
                    read_only: 1,
                    default: trainee_name
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    fieldname: 'remarks',
                    fieldtype: 'Small Text',
                    label: __('Remarks')
                }
            ], function(values) {
                frappe.call({
                    method: 'microsynth.qms.doctype.competency_instruction.competency_instruction.create_and_submit_instruction',
                    args: {
                        instructor: values.instructor,
                        date: values.date,
                        trainee: values.trainee,
                        competency_assignment: row.name,
                        remarks: values.remarks || ''
                    },
                    callback: function(response) {
                        const name = response && response.message;
                        if (!name) {
                            frappe.msgprint({
                                title: __('Instruction could not be submitted'),
                                message: __('The server did not return a document name.'),
                                indicator: 'red'
                            });
                            return;
                        }

                        row.competency_instruction = name;
                        if (frm && frm.fields_dict && frm.fields_dict.competencies) {
                            frm.fields_dict.competencies.grid.refresh();
                        }

                        frappe.set_route('Form', 'Competency Instruction', name);
                    }
                });
            }, __('Confirm Instruction'), __('Submit'));
        }
    });
}


function sync_competency_instruction_buttons(frm) {
    const rows = frm.doc.competencies || [];
    const competencyNames = [...new Set(rows.map(row => row.competency).filter(Boolean))];
    if (!competencyNames.length) {
        rows.forEach(row => {
            row.requires_on_the_job_instruction = 0;
            row.competency_instruction = row.competency_instruction || '';
        });
        frm.fields_dict.competencies.grid.refresh();
        return;
    }

    frappe.call({
        method: 'microsynth.qms.doctype.competency.competency.get_on_the_job_instruction_requirements',
        args: {
            competency_names: competencyNames
        },
        callback: function(response) {
            const requirements = response.message || {};
            rows.forEach(row => {
                row.requires_on_the_job_instruction = requirements[row.competency] ? 1 : 0;
            });

            rows.forEach(row => {
                if (!row.name) {
                    return;
                }
                frappe.call({
                    method: 'microsynth.qms.doctype.competency_instruction.competency_instruction.get_linked_instruction_for_assignment',
                    args: { competency_assignment: row.name },
                    callback: function(link_response) {
                        const linked = link_response && link_response.message;
                        row.competency_instruction = linked || row.competency_instruction || '';
                    }
                });
            });

            frm.fields_dict.competencies.grid.refresh();
        }
    });
}


function show_signing_banner(frm) {
    let missing_signature = [];

    if (!frm.doc.employee_signed_on || !frm.doc.employee_user || !frm.doc.employee_signature) {
        missing_signature.push(__('Employee'));
    }

    if (!frm.doc.process_owner_signed_on || !frm.doc.process_owner || !frm.doc.process_owner_signature) {
        missing_signature.push(__('Process Owner'));
    }
    console.log('Missing signatures:', missing_signature);
    frm.dashboard.clear_comment();
    if (missing_signature.length > 0) {
        frm.dashboard.add_comment(
            __('<b>Missing signature:</b> ') + missing_signature.join(', '),
            'red',
            true
        );
    }
}


function add_sign_button_if_allowed(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.staff_profile.staff_profile.get_signing_users',
        'args': {
            'employee': frm.doc.employee
        },
        'callback': function(response) {
            const data = response.message || {};
            const employee_user = data.employee_user;
            const process_owner = data.process_owner;
            const current_user = frappe.session.user;

            if (current_user === employee_user && !frm.doc.employee_signed_on) {
                frm.page.clear_primary_action();
                frm.page.set_primary_action(__('Sign'), function() {
                    sign_staff_profile(frm, 'employee');
                });
                return;
            }

            if (current_user === process_owner && !frm.doc.process_owner_signed_on) {
                frm.page.clear_primary_action();
                frm.page.set_primary_action(__('Sign'), function() {
                    sign_staff_profile(frm, 'process_owner');
                });
            }
        }
    });
}


function sign_staff_profile(frm, role) {
    frappe.prompt(
        [
            { fieldname: 'password', fieldtype: 'Password', label: __('Approval Password'), reqd: 1 }
        ],
        function(values) {
            frappe.call({
                'method': 'microsynth.qms.doctype.staff_profile.staff_profile.sign_staff_profile',
                'args': {
                    'docname': frm.doc.name,
                    'user': frappe.session.user,
                    'password': values.password,
                    'role': role
                },
                'callback': function(response) {
                    if (response.message) {
                        frm.reload_doc();
                    }
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}


function create_new_version(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.staff_profile.staff_profile.create_new_version',
        'args': {
            'docname': frm.doc.name
        },
        'callback': function(response) {
            if (response.message && response.message.name) {
                frappe.set_route('Form', 'Staff Profile', response.message.name);
            }
        }
    });
}
