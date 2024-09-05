// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customs Declaration', {
	refresh: function(frm) {
		if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__("Download Front Page"), function() {
                var w = window.open(
                    frappe.urllib.get_full_url("/api/method/microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_partial_pdf"  
                            + "?doc=" + encodeURIComponent(frm.doc.name)
                            + "&part=front")
                );
                if (!w) {
                    frappe.msgprint(__("Please enable pop-ups")); return;
                }
            });
			frm.add_custom_button(__("Download AT"), function() {
                var w = window.open(
                    frappe.urllib.get_full_url("/api/method/microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_partial_pdf"  
                            + "?doc=" + encodeURIComponent(frm.doc.name)
                            + "&part=AT")
                );
                if (!w) {
                    frappe.msgprint(__("Please enable pop-ups")); return;
                }
            });
			frm.add_custom_button(__("Download EU"), function() {
                var w = window.open(
                    frappe.urllib.get_full_url("/api/method/microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_partial_pdf"  
                            + "?doc=" + encodeURIComponent(frm.doc.name)
                            + "&part=EU")
                );
                if (!w) {
                    frappe.msgprint(__("Please enable pop-ups")); return;
                }
            });
        }

	}
});
