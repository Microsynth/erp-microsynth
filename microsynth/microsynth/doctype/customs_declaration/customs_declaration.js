// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customs Declaration', {
	refresh: function(frm) {
		if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__("Print Front Page"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_partial_pdf",
                    "args": {
                        "doc":frm.doc.name,
						"part": "front"
                    }
                })
            });
			frm.add_custom_button(__("Print AT"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_partial_pdf",
                    "args": {
                        "doc":frm.doc.name,
						"part": "AT"
                    }
                })
            });
			frm.add_custom_button(__("Print EU"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_partial_pdf",
                    "args": {
                        "doc":frm.doc.name,
						"part": "EU"
                    }
                })
            });
        }

	}
});
