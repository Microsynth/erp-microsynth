frappe.listview_settings['Customs Declaration'] = {
    onload: function(listview) {
        listview.page.add_menu_item( __("Create Customs Declaration"), function() {
            create_customs_declaration();
        });
    }
}

function create_customs_declaration(date, company) {
    frappe.call({
        "method": "microsynth.microsynth.doctype.customs_declaration.customs_declaration.create_customs_declaration",
        "callback": function(response) {
            if (response.message) {
                // redirect to the new record
                window.location.href = response.message;
            } else {
                // no records found
                frappe.show_alert( __("No suitable delivery notes found.") );
            }
        }
    });
}
