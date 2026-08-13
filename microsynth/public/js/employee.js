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

frappe.ui.form.on('Employee', {
    onload(frm) {
        frm._last_auto_visa = '';
        set_default_visa(frm);
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
