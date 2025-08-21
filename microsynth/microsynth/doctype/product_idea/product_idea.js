// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product Idea', {
	refresh: function(frm) {
		frm.add_custom_button(__('Overview'), function() {
			frappe.set_route('query-report', 'Product Ideas');
		});
	}
});
