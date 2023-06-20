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
    var recipient = frm.doc.email || frm.doc.email_id || frm.doc.contact_email || "";
    var cc = "";
    var subject = "Microsynth Payment Reminder";
    /* if (frm.doc.highest_level === 2) {
        subject = "Mahnung";
    } else if (frm.doc.highest_level === 3) {
        subject = "Zweite Mahnung";
    } */

    new frappe.views.CommunicationComposer({
		doc: {
		    doctype: frm.doc.doctype,
		    name: frm.doc.name
		},
		subject: subject + " " + frm.doc.name,
		cc:  cc,
		recipients: recipient,
		attach_document_print: true,
		message: get_email_body(frm)
	});
}

function get_email_body(frm) {
    var html = "<p>" + __("Dear Sir or Madam", frm.doc.language) + "</p>"
        + "<p><br></p>";
    
    if (frm.doc.highest_level === 1) {
        html += "<p>Im hektischen Alltag kann es schnell einmal vorkommen eine fällige Zahlung zu übersehen..."
                + "<br><br>Wir bitten Sie höflich um Zahlung der fälligen angehängten Rechnung in den nächsten 5 Tagen."
             + "<br><br>Sollten Sie die Zahlung bereits veranlasst haben, bitten wir um Information, wann Ihre Zahlung auf welches Konto erfolgt ist.</p>";
    } else if (frm.doc.highest_level === 2) {
        html += "<p>Wir haben Ihnen bereits eine Zahlungserinnerung zukommen lassen."
             + "<br><br><i>Hat es einen Grund für die ausstehende Zahlung?</i>"
             + "<br> - Dann kontaktieren Sie uns bitte, wir finden sicher eine gemeinsame Lösung"
             + "<br><br><i>Haben Sie bereits bezahlt?</i>"
             + "<br>- Bitte geben Sie uns das Valutadatum und das begünstigte Konto an, damit wir der Zahlung nachgehen können"
             + "<br><br><i>Haben Sie es einfach vergessen?</i>"
             +"<br>- Kein Problem, gleichen Sie die Rechnung innert den nächsten 3 Tagen aus. Vielen Dank im Voraus!</p>";
    } else {
        html += "<p>Leider konnten wir trotz mehreren Schreiben noch keinen Zahlungseingang für die überfällige Rechnung feststellen. "
             + "<br><br>Bitte haben Sie dafür Verständnis, dass wir uns als nächsten Schritt weitere Massnahmen vorbehalten."
             + "<br><br>Bitte vermeiden Sie diese Umtriebe und Kosten und nehmen die Zahlung innert den nächsten drei Tagen vor, vielen Dank im Voraus!</p>";
    }
    html += "<p><br></p>"
         + "<p>Sollten Sie noch Fragen haben, stehen wir gerne zur Verfügung.</p>"
         + "<p><br></p>";
    
    return html;
}