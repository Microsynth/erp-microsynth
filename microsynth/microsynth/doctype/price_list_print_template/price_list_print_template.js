// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Price List Print Template', {
	refresh: function(frm) {
		frm.add_custom_button(__("Render & Download"), function() {
			var w = window.open(
				frappe.urllib.get_full_url("/api/method/microsynth.microsynth.webshop.get_price_list_doc"
						+ "?contact=245438")
			);
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups")); return;
			}
		});
	}
});
