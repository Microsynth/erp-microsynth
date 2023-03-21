/* Custom script extension for Sales Invoice */
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        prepare_naming_series(frm);				// common function
        
        if (frm.doc.docstatus == 0 && frm.doc.net_total > 0) {
            frm.add_custom_button(__("Allocate credit"), function() {
                allocate_credits(frm);
            });
        };
        if (frm.doc.docstatus > 0) {
            frm.add_custom_button(__("Clone"), function() {
                clone(frm);
            });
        };
    },
    company(frm) {
        set_naming_series(frm);					// common function
    },
    on_submit(frm) {
        if (frm.doc.total_customer_credit > 0) {
            book_credits(frm.doc.name);
        }
    },
    before_cancel(frm) {
        if (frm.doc.total_customer_credit > 0) {
            cancel_credit_journal_entry(frm.doc.name)
        }
    }
});

frappe.ui.form.on('Sales Invoice Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});

function clone(frm) {
    frappe.call({
        'method': "microsynth.microsynth.utils.exact_copy_sales_invoice",
        'args': {
            'sales_invoice': frm.doc.name
        },
        'callback': function(r)
        {
            frappe.set_route("Form", "Sales Invoice", r.message)
        }
    });
}

function allocate_credits(frm) {
    frappe.call({
        'method': "microsynth.microsynth.credits.allocate_credits_to_invoice",
        'args': {
            'sales_invoice': frm.doc.name
        },
        'callback': function(r)
        {
            cur_frm.reload_doc();
            frappe.show_alert( __("allocated credits") );
        }
    });
}

function book_credits(sales_invoice) {
    frappe.call({
        'method': "microsynth.microsynth.credits.book_credit",
        'args': { 
            'sales_invoice': sales_invoice 
        },
        'callback': function(r)
        {
            frappe.show_alert( __("booked credits"));
        }
    });
}

function cancel_credit_journal_entry(sales_invoice) {
    frappe.call({
        'method': "microsynth.microsynth.credits.cancel_credit_journal_entry",
        'args': { 
            'sales_invoice': sales_invoice 
        },
        'callback': function(r)
        {
            frappe.show_alert( __("cancelled " + r.message));
        }
    });
}