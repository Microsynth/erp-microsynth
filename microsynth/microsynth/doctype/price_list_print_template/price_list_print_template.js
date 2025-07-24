// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Price List Print Template', {
    refresh: function(frm) {
        frm.add_custom_button(__("Render & Download"), function() {
            const d = new frappe.ui.Dialog({
                'title': __("Select Contact"),
                'fields': [
                    {
                        label: __("Contact"),
                        fieldname: "contact",
                        fieldtype: "Link",
                        options: "Contact",
                        reqd: 1,
                        default: "222010"
                    }
                ],
                'primary_action_label': __("Download"),
                primary_action(values) {
                    const encodedContact = encodeURIComponent(values.contact);
                    const url = frappe.urllib.get_full_url(
                        "/api/method/microsynth.microsynth.webshop.get_price_list_doc?contact=" + encodedContact
                    );
                    const w = window.open(url);
                    if (!w) {
                        frappe.msgprint(__("Please enable pop-ups"));
                    }
                    d.hide();
                }
            });

            d.show();
        });
    }
});
