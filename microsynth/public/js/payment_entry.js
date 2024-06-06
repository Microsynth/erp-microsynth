/* this script requires locals.account_matrix and locals.cost_center_matrix */
/* Custom script extension for Sales Order */
frappe.ui.form.on('Payment Entry', {
    refresh(frm) {
        check_display_unallocated_warning(frm);
        
    },
    unallocated_amount(frm) {
        check_display_unallocated_warning(frm);
    },
    difference_amount(frm) {
        check_display_unallocated_warning(frm);
    },
    validate: function(frm) {
        if (frm.doc.references) {
            for (var i= 0; i < frm.doc.references.length; i++) {
                if (frm.doc.references[i].outstanding_amount > frm.doc.references[i].allocated_amount) {
                    frappe.msgprint( __("Warning, Outstanding > Allocated in row " + (i+1) + ".", __("Validation") ));
                    break;
                }
            }
        }
    },
    before_save: function(frm) {
        // hotfix: check for < 0.01 allocations
        if ((frm.doc.references) && (frm.doc.references.length > 0)) {
            for (var i = 0; i < frm.doc.references.length; i++) {
                var delta = Math.abs(frm.doc.references[i].outstanding_amount - frm.doc.references[i].allocated_amount);
                console.log(i + ": delta=" + delta);
                if ((delta < 0.01) && (delta > 0)) {
                    frappe.model.set_value(frm.doc.references[i].doctype, frm.doc.references[i].name, 'allocated_amount', frm.doc.references[i].outstanding_amount);
                }
            }
        }
    }
});

function check_display_unallocated_warning(frm) {
    if (Math.round(100 * Math.abs(cur_frm.doc.unallocated_amount || cur_frm.doc.difference_amount || 0)) > 0) {
        cur_frm.dashboard.clear_comment();
        cur_frm.dashboard.add_comment(__('This document has an unallocated amount.'), 'red', true);
    } else {
        cur_frm.dashboard.clear_comment();
    }
}
