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

        if (!frm.is_new() && frm.doc.docstatus === 0 && (!frm.doc.status || frm.doc.status === 'Draft') && frm.perm[0].write) {
            frm.add_custom_button(__('Add Department competencies'), function() {
                add_department_competencies(frm);
            });
            add_template_competencies_button(frm);
        }
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


function add_department_competencies(frm) {
    if (!frm.doc.employee) {
        frappe.msgprint(__('Please select an Employee first.'));
        return;
    }
    const employee = frm.doc.employee;
    frappe.call({
        'method': 'microsynth.qms.doctype.staff_profile.staff_profile.get_department_competencies',
        'args': { 'docname': frm.doc.name, 'employee': employee },
        'callback': function(response) {
            if (frm.doc.employee !== employee) {
                return;
            }
            const assigned = new Set((frm.doc.competencies || []).map(row => row.competency));
            const competencies = (response.message || []).filter(row => !assigned.has(row.name));
            if (!competencies.length) {
                frappe.msgprint(__('No additional valid competencies are available for this employee\'s departments.'));
                return;
            }
            const dialog = new frappe.ui.Dialog({
                title: __('Add Department competencies'),
                size: 'large',
                fields: [{ fieldname: 'competency_selection', fieldtype: 'HTML' }],
                primary_action_label: __('Add'),
                primary_action: function() {
                    if (frm.doc.employee !== employee || frm.doc.docstatus !== 0 || (frm.doc.status && frm.doc.status !== 'Draft')) {
                        frappe.msgprint(__('The Staff Profile has changed. Please reopen the competency selection.'));
                        dialog.hide();
                        return;
                    }
                    const existing = new Set((frm.doc.competencies || []).map(row => row.competency));
                    let added = false;
                    $list.find('input:checked').each(function() {
                        const competency = competencies[Number($(this).val())];
                        if (existing.has(competency.name)) {
                            return;
                        }
                        frm.add_child('competencies', {
                            competency: competency.name,
                            competency_title: competency.title,
                            status: 'Planned',
                            responsibility_role: 'Main'
                        });
                        existing.add(competency.name);
                        added = true;
                    });
                    if (added) {
                        frm.dirty();
                        frm.refresh_field('competencies');
                        sync_competency_instruction_buttons(frm);
                    }
                    dialog.hide();
                }
            });
            const $wrapper = dialog.fields_dict.competency_selection.$wrapper;
            const $actions = $('<div class="clearfix" style="margin-bottom: 12px;"></div>').appendTo($wrapper);
            const $list = $('<div style="max-height: 55vh; overflow-y: auto;"></div>').appendTo($wrapper);
            $('<button type="button" class="btn btn-default btn-sm"></button>')
                .text(__('Select all')).appendTo($actions)
                .on('click', () => $list.find('input').prop('checked', true));
            $('<button type="button" class="btn btn-default btn-sm" style="margin-left: 8px;"></button>')
                .text(__('Deselect all')).appendTo($actions)
                .on('click', () => $list.find('input').prop('checked', false));

            competencies.forEach((competency, index) => {
                const $label = $('<label style="display: flex; align-items: baseline; gap: 8px; padding: 8px; border-bottom: 1px solid #eee; font-weight: normal; cursor: pointer;"></label>')
                    .appendTo($list);
                $('<input type="checkbox">').val(index).appendTo($label);
                const $text = $('<span></span>').appendTo($label);
                $('<strong></strong>').text(competency.title || competency.name).appendTo($text);
                $('<small class="text-muted" style="display: block;"></small>').text(competency.name).appendTo($text);
            });
            dialog.show();
        }
    });
}


function add_template_competencies_button(frm) {
    if (!frm.doc.employee) {
        return;
    }
    const employee = frm.doc.employee;
    frappe.call({
        'method': 'microsynth.qms.doctype.staff_profile.staff_profile.get_linked_staff_profile_template',
        'args': {
            'docname': frm.doc.name,
            'employee': employee
        },
        'callback': function(response) {
            if (frm.doc.employee !== employee || frm.is_new() || frm.doc.docstatus !== 0 || (frm.doc.status && frm.doc.status !== 'Draft')) {
                return;
            }
            const template = response.message || {};
            if (!template.template_name) {
                return;
            }
            frm.add_custom_button(__('Add Template competencies'), function() {
                add_template_competencies(frm, template.template_name);
            });
        }
    });
}


function add_template_competencies(frm, template_name) {
    if (!frm.doc.employee) {
        frappe.msgprint(__('Please select an Employee first.'));
        return;
    }
    const employee = frm.doc.employee;
    validate_staff_profile_template(template_name, function(validatedTemplateName) {
        frappe.call({
            'method': 'microsynth.qms.doctype.staff_profile.staff_profile.get_linked_template_competencies',
            'args': {
                'docname': frm.doc.name,
                'employee': employee,
                'template_name': validatedTemplateName
            },
            'callback': function(response) {
                if (frm.doc.employee !== employee || frm.doc.docstatus !== 0 || (frm.doc.status && frm.doc.status !== 'Draft')) {
                    frappe.msgprint(__('The Staff Profile has changed. Please reopen the template competency action.'));
                    return;
                }
                const data = response.message || {};
                const competencies = data.competencies || [];
                const existing = new Set((frm.doc.competencies || []).map(row => row.competency));
                let added = 0;

                competencies.forEach(function(competency) {
                    if (!competency.competency || existing.has(competency.competency)) {
                        return;
                    }

                    frm.add_child('competencies', competency);
                    existing.add(competency.competency);
                    added += 1;
                });
                if (!added) {
                    frappe.msgprint(
                        __('No additional valid competencies are available from Staff Profile Template {0}.', [data.template_title || data.template_name || template_name])
                    );
                    return;
                }
                frm.dirty();
                frm.refresh_field('competencies');
                sync_competency_instruction_buttons(frm);
            }
        });
    });
}


function validate_staff_profile_template(template_name, callback) {
    frappe.call({
        'method': 'microsynth.qms.doctype.staff_profile_template.staff_profile_template.validate_template_for_staff_profile',
        'args': {
            'template_name': template_name
        },
        'callback': function(response) {
            const result = response.message || {};
            if (!result.valid) {
                frappe.msgprint({
                    title: __('Invalid Competencies'),
                    message: result.message || __('This template has invalid competencies.'),
                    indicator: 'red'
                });
                return;
            }
            callback(template_name);
        }
    });
}


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
        'method': 'microsynth.qms.doctype.competency_instruction.competency_instruction.has_submitted_instruction_for_assignment',
        'args': {
            'competency_assignment': row.name
        },
        'callback': function(response) {
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
        'method': 'frappe.client.get',
        'args': {
            'doctype': 'Employee',
            'name': trainee_default || ''
        },
        'callback': function(response) {
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
                    'method': 'microsynth.qms.doctype.competency_instruction.competency_instruction.create_and_submit_instruction',
                    'args': {
                        'instructor': values.instructor,
                        'date': values.date,
                        'trainee': values.trainee,
                        'competency_assignment': row.name,
                        'remarks': values.remarks || ''
                    },
                    'callback': function(response) {
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
        'method': 'microsynth.qms.doctype.competency.competency.get_on_the_job_instruction_requirements',
        'args': {
            'competency_names': competencyNames
        },
        'callback': function(response) {
            const requirements = response.message || {};
            rows.forEach(row => {
                row.requires_on_the_job_instruction = requirements[row.competency] ? 1 : 0;
            });
            rows.forEach(row => {
                if (!row.name) {
                    return;
                }
                frappe.call({
                    'method': 'microsynth.qms.doctype.competency_instruction.competency_instruction.get_linked_instruction_for_assignment',
                    'args': { 'competency_assignment': row.name },
                    'callback': function(link_response) {
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
