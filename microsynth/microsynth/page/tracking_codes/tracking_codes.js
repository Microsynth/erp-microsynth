frappe.pages['tracking_codes'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Tracking Codes',
		single_column: true
	});
}