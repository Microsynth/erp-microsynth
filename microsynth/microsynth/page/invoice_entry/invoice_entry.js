frappe.pages['invoice_entry'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Invoice Entry',
		single_column: true
	});
}