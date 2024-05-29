frappe.ui.form.on('Payment Reminder', {
    refresh(frm) {
        $("span[data-label='Email']").parent().parent().remove();   // remove Menu > Email
        
        if (frm.doc.docstatus === 1) {
            if ((frm.doc.docstatus === 1) && (document.getElementsByClassName("fa-envelope-o").length === 0)) {
                cur_frm.page.add_action_icon(__("fa fa-envelope-o"), function() {
                    custom_mail_dialog(frm);
                });
            }
        }
        prepare_email_subject(frm);
        prepare_email_body(frm);
    },
    validate(frm) {
        // check if invoices have been transmitted
        for (var i = 0; i < frm.doc.sales_invoices.length; i++) {
            if (!frm.doc.sales_invoices[i].invoice_sent_on) {
                frappe.msgprint( __("Invoice {0} seems to be not transmitted. Please check.").replace("{0}", frm.doc.sales_invoices[i].sales_invoice), __("Validation") );
                frappe.validated=false;
            }
        }
    }
});


function custom_mail_dialog(frm) {
    var recipient = frm.doc.email;
    var cc = "";
    if (!locals.email_body || !locals.email_subject) {
        frappe.show_alert( __("Please wait a second and try again.") );
        prepare_email_subject(frm);
        prepare_email_body(frm);
    } else {
        new frappe.views.CommunicationComposer({
            doc: {
                doctype: frm.doc.doctype,
                name: frm.doc.name
            },
            subject: locals.email_subject,
            cc: cc,
            recipients: recipient,
            attach_document_print: true,
            message: locals.email_body + "<p><b style=\"color: #e65023;\">Microsynth</b> • Schützenstrasse 15 • CH-9436 Balgach • www.microsynth.com</p>"
        });
    }    
}


function prepare_email_subject(frm) {
    frappe.call({
        'method': "microsynth.microsynth.payment_reminder.get_email_subject",
        'args': {
            'prm': frm.doc.name
        },
        'asyc': false,
        'callback': function(response) {
            locals.email_subject = response.message
        }
    });
}


function prepare_email_body(frm) {
    frappe.call({
        'method': "microsynth.microsynth.payment_reminder.get_html_message",
        'args': {
            'prm': frm.doc.name
        },
        'asyc': false,
        'callback': function(response) {
            locals.email_body = response.message
        }
    });
}
