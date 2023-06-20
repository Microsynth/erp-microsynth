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
	}
});

function custom_mail_dialog(frm) {
    var recipient = frm.doc.email;
    var cc = "";

    new frappe.views.CommunicationComposer({
		doc: {
		    doctype: frm.doc.doctype,
		    name: frm.doc.name
		},
		subject: get_email_subject(frm),
		cc:  cc,
		recipients: recipient,
		attach_document_print: true,
		message: get_email_body(frm)
	});
}

function get_email_subject(frm) {
    if (frm.doc.language == "de") {
        if (frm.doc.highest_level == 1 ) {
            var subject = "Microsynth Zahlungserinnerung " + frm.doc.name
        }
        else if (frm.doc.highest_level == 2){
            var subject = "Microsynth Mahnung " + frm.doc.name
        }
        else if (frm.doc.highest_level == 3){
            var subject = "Microsynth Mahnung " + frm.doc.name
        }
        else {
            var subject = "Microsynth Mahnung " + frm.doc.name
        }
    }
    else {
        var subject = "Microsynth Payment Reminder " + frm.doc.name
    }
    return subject
}

function get_email_body(frm) {
    if (frm.doc.language == "de") {
        var html = "<p>Sehr geehrte Damen und Herren</p>"
        html += "<p><br></p>";

        if (frm.doc.highest_level == 1 ) {
            html += "<p>Die nachfolgende(n) Rechnung(en) war(en) bereits zur Zahlung fällig. Vermutlich ist es Ihrer Aufmerksamkeit entgangen, diese rechtzeitig zu begleichen. Wir wären Ihnen sehr dankbar für eine rasche Überweisung.</p>";
            html += "<p>Sollten Sie Fragen zur Rechnungsaufstellung haben, so freuen wir uns sehr, von Ihnen zu hören. Sollte sich die Zahlung mit dieser Nachricht überschnitten haben, so bitten wir Sie, diese als hinfällig zu betrachten.</p>";
        }
        else if (frm.doc.highest_level == 2) {
            html += "<p>In der Hektik des geschäftlichen Alltags kommt es vor, dass Zahlungen vergessen werden. Gerne erinnern wir Sie daher ein zweites Mal an diese noch offene(n) Rechnung(en). Sollte es Unklarheiten zu der Rechnung geben, so würde es uns freuen, diese mit Ihnen zu klären. Andernfalls wären wir für eine umgehende Überweisung dankbar. Sollte sich die Zahlung mit dieser Nachricht überschnitten haben, so bitten wir Sie, diese als hinfällig zu betrachten.</p>";
        }
        else if (frm.doc.highest_level == 3) {
            html += "<p>In der Hektik des geschäftlichen Alltags kommt es vor, dass Zahlungen vergessen werden. Gerne erinnern wir Sie daher ein zweites Mal an diese noch offene(n) Rechnung(en). Sollte es Unklarheiten zu der Rechnung geben, so würde es uns freuen, diese mit Ihnen zu klären. Andernfalls wären wir für eine umgehende Überweisung dankbar. Sollte sich die Zahlung mit dieser Nachricht überschnitten haben, so bitten wir Sie, diese als hinfällig zu betrachten.</p>";
        }
        else {
            html += "<p>Unserer Buchhaltung zufolge ist diese Rechnung vom 02.12.2019 auch nach unserer 1. Mahnung vom  und 2. Mahnung vom  immer noch nicht beglichen. Bitte überweisen Sie den fälligen Betrag zur Vermeidung weiterer Schritte unverzüglich auf unser Konto. Zahlungseingänge sind bis und mit gestern berücksichtig. Sollte sich Ihre Zahlung mit unserem Schreiben gekreuzt haben, bitten wir Sie, dieses als gegenstandslos zu betrachten.</p>";
        }
        html += "<p><br>Beste Grüsse<br>Microsynth Administration<br><br></p>";
    }
    // else if (frm.doc.language == "fr") {
    //     var html = "<p>Dear Sir or Madam</p>"
    //     html += "<p><br></p>";

    //     if (frm.doc.highest_level == 1 ) {
    //         html += "<p>The following invoice(s) has(have) already been due for payment. We assume that the punctual payment has escaped your notice and would be grateful for a rapid settlement of the invoice(s).</p>";
    //         html += "<p>If you have any questions about the invoice(s), please feel free to contact us. If the payment has already been authorized, please ignore this message.</p>";
    //     }
    //     else if (frm.doc.highest_level == 2) {
    //         html += "<p>Everyday business life can be hectic and invoices can be forgotten. We would therefore like to remind you a second time that the following invoice(s) is(are) due for payment. Should you have questions about the invoice(s), please feel free to contact us. Otherwise, we would be grateful for an immediate payment. If the payment has already been authorized, please ignore this message.</p>";
    //     }
    //     else if (frm.doc.highest_level == 3) {
    //         html += "<p>Everyday business life can be hectic and invoices can be forgotten. We would therefore like to remind you a second time that the following invoice(s) is(are) due for payment. Should you have questions about the invoice(s), please feel free to contact us. Otherwise, we would be grateful for an immediate payment. If the payment has already been authorized, please ignore this message.</p>";
    //     }
    //     else {
    //         html += "<p>As per our accounting department, this invoice(s) is (are) due for payment since a long time. Please check the invoice and report any dissension immediately to Microsynth AG.</p>";
    //     }
    //     html += "<p><br></p>";
    //     html += "<p>" + frm.doc.company + "</p>";
    // }
    else {
        var html = "<p>Dear Sir or Madam</p>"
        html += "<p><br></p>";

        if (frm.doc.highest_level == 1 ) {
            html += "<p>The following invoice(s) has(have) already been due for payment. We assume that the punctual payment has escaped your notice and would be grateful for a rapid settlement of the invoice(s).</p>";
            html += "<p>If you have any questions about the invoice(s), please feel free to contact us. If the payment has already been authorized, please ignore this message.</p>";
        }
        else if (frm.doc.highest_level == 2) {
            html += "<p>Everyday business life can be hectic and invoices can be forgotten. We would therefore like to remind you a second time that the following invoice(s) is(are) due for payment. Should you have questions about the invoice(s), please feel free to contact us. Otherwise, we would be grateful for an immediate payment. If the payment has already been authorized, please ignore this message.</p>";
        }
        else if (frm.doc.highest_level == 3) {
            html += "<p>Everyday business life can be hectic and invoices can be forgotten. We would therefore like to remind you a second time that the following invoice(s) is(are) due for payment. Should you have questions about the invoice(s), please feel free to contact us. Otherwise, we would be grateful for an immediate payment. If the payment has already been authorized, please ignore this message.</p>";
        }
        else {
            html += "<p>As per our accounting department, this invoice(s) is (are) due for payment since a long time. Please check the invoice and report any dissension immediately to Microsynth AG.</p>";
        }
        html += "<p><br>Best regards<br>Microsynth Administration<br><br></p>";
    }

    html += "<p><b style=\"color: #e65023;\">Microsynth</b> • Schützenstrasse 15 • CH-9436 Balgach • www.microsynth.com</p>"
    // html += "<p style=\"font-size: 7pt; color: grey;\">MWST Nr. (VAT): CHE-107.542.107MWST</p>"

    return html;
}