try {
    cur_frm.dashboard.add_transactions([
        {
            'label': 'Lifecycle',
            'items': ['Employee Onboarding']
        }
    ]);
} catch { /* do nothing */ }

function get_visa_from_name(frm) {
    const first_name = (frm.doc.first_name || '').trim();
    const last_name = (frm.doc.last_name || '').trim();

    if (!first_name || !last_name) {
        return '';
    }

    return first_name.slice(0, 1) + last_name.slice(0, 2);
}

function set_default_visa(frm) {
    const visa_from_name = get_visa_from_name(frm);
    if (!visa_from_name) {
        return;
    }

    const current_visa = (frm.doc.visa || '').trim();
    const last_auto_visa = (frm._last_auto_visa || '').trim();
    const can_autofill = !current_visa || (last_auto_visa && current_visa === last_auto_visa);

    if (!can_autofill) {
        return;
    }

    frm._last_auto_visa = visa_from_name;

    if (current_visa !== visa_from_name) {
        frm.set_value('visa', visa_from_name);
    }
}

function get_emergency_contact_values(frm) {
    return {
        emergency_contact: frm.doc.person_to_be_contacted || '',
        emergency_phone: frm.doc.emergency_phone_number || '',
        emergency_relation: frm.doc.relation || ''
    };
}

function show_emergency_contact_dialog(frm) {
    const values = get_emergency_contact_values(frm);
    const dialog = new frappe.ui.Dialog({
        title: __('Edit Emergency Contact'),
        fields: [
            {
                fieldtype: 'Data',
                fieldname: 'emergency_contact',
                label: __('Emergency Contact'),
                reqd: 1,
                default: values.emergency_contact
            },
            {
                fieldtype: 'Data',
                fieldname: 'emergency_phone',
                label: __('Emergency Phone'),
                reqd: 1,
                default: values.emergency_phone
            },
            {
                fieldtype: 'Data',
                fieldname: 'emergency_relation',
                label: __('Relation'),
                default: values.emergency_relation
            }
        ],
        primary_action_label: __('Save'),
        primary_action(dialog_values) {
            frappe.call({
                method: 'microsynth.microsynth.hr.update_employee_emergency_contact',
                args: {
                    employee: frm.doc.name,
                    emergency_contact: dialog_values.emergency_contact,
                    emergency_phone: dialog_values.emergency_phone,
                    emergency_relation: dialog_values.emergency_relation
                },
                freeze: true,
                freeze_message: __('Saving emergency contact...'),
                callback() {
                    dialog.hide();
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __('Emergency contact updated.'),
                        indicator: 'green'
                    });
                }
            });
        }
    });
    dialog.show();
}

frappe.ui.form.on('Employee', {
    onload(frm) {
        frm._last_auto_visa = '';
        set_default_visa(frm);
    },
    refresh(frm) {
        if (frm.is_new()) {
            return;
        }

        frm.add_custom_button(__('Edit Emergency Contact'), () => {
            show_emergency_contact_dialog(frm);
        });
    },
    first_name(frm) {
        set_default_visa(frm);
    },
    last_name(frm) {
        set_default_visa(frm);
    },
    visa(frm) {
        const current_visa = (frm.doc.visa || '').trim();
        const last_auto_visa = (frm._last_auto_visa || '').trim();

        if (current_visa && current_visa !== last_auto_visa) {
            frm._last_auto_visa = '';
        }
    },
    before_save(frm) {
        set_default_visa(frm);
    }
});
