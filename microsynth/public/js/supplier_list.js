// Copyright (c) 2025, Microsynth
// For license information, please see license.txt


var global_onload = frappe.listview_settings['Supplier'].onload;
frappe.listview_settings['Supplier'].onload = function (doclist) {
    if (global_onload) {
        global_onload(doclist);
    }
    //add_clear_button();
    add_simplified_supplier_button();
}


// Add a green "New (simplified)" button to the Supplier List
function add_simplified_supplier_button() {
    // Only add on Supplier List
    if (cur_list && cur_list.doctype === "Supplier") {
        var filter_bar = document.getElementsByClassName("page-form");
        if (!filter_bar || filter_bar.length === 0) return;

        // Prevent duplicate buttons on reload
        if (document.getElementById("btn_new_simplified")) return;
        var btn = document.createElement("div");
        btn.setAttribute('class', 'form-group frappe-control input-max-width col-md-2');
        btn.innerHTML = `
            <button id="btn_new_simplified" class="btn btn-success">
                ${__("New (simplified)")}
            </button>
        `;
        for (var i = 0; i < filter_bar.length; i++) {
            filter_bar[i].appendChild(btn);
        }
        // Bind click action
        document.getElementById("btn_new_simplified").onclick = function () {
            document.getElementById("btn_new_simplified").onclick = function () {
                // TODO: Why is it necessary to click twice the first time?
                open_simplified_supplier_creation_dialog();
            };
        };
    }
}


function open_simplified_supplier_creation_dialog() {
    const d = new frappe.ui.Dialog({
        'title': __("Create Supplier, Contact and Address"),
        'fields': [
            // Supplier
            { fieldtype: "Section Break", label: __("Supplier") },
            {
                fieldtype: "Data",
                fieldname: "supplier_name",
                reqd: 1,
                label: __("Supplier Name"),
                change: function () {
                    let name = d.get_value("supplier_name");
                    if (!name) return;
                    frappe.call({
                        'method': "microsynth.microsynth.purchasing.check_existing_supplier",
                        'args': { 'supplier_name': name },
                        'callback': function (r) {
                            if (r.message && r.message.exists) {
                                frappe.msgprint({
                                    'title': __("Already Existing Supplier Name"),
                                    'message': __("A Supplier with this name already exists: ") +
                                             `<a href="/desk#Form/Supplier/${r.message.supplier}">${r.message.supplier}</a>`,
                                    'indicator': "red"
                                });
                            }
                        }
                    });
                }
            },
            {
                fieldtype: "Link",
                fieldname: "country",
                reqd: 1,
                label: __("Country"),
                options: "Country",
                change: function () {
                    const c = d.get_value("country");
                    if (c) d.set_value("address_country", c);
                }
            },
            { fieldtype: "Link", fieldname: "webshop_company", reqd: 1, label: __("Company"), options: "Company", default: "Microsynth AG" },

            { fieldtype: "Column Break" },

            { fieldtype: "Link", fieldname: "billing_currency", reqd: 1, label: __("Billing Currency"), options: "Currency" },

            { fieldtype: "Data", fieldname: "tax_id", label: __("Tax ID") },

            { fieldtype: "Data", fieldname: "webshop_url", label: __("Webshop URL") },

            // Contact
            { fieldtype: "Section Break", label: __("Order Contact") },

            { fieldtype: "Link", fieldname: "salutation", label: __("Salutation"), options: "Salutation" },

            { fieldtype: "Data", fieldname: "first_name", reqd: 1, label: __("First Name") },

            { fieldtype: "Data", fieldname: "email", reqd: 1, label: __("Email") },

            { fieldtype: "Column Break" },

            { fieldtype: "Select", fieldname: "title", label: __("Title"), options: "\nDr.\nProf.\nProf. Dr." },

            { fieldtype: "Data", fieldname: "last_name", label: __("Last Name") },

            { fieldtype: "Data", fieldname: "phone", label: __("Phone Number") },

            // Address
            { fieldtype: "Section Break", label: __("Address") },

            { fieldtype: "Data", fieldname: "address_line1", reqd: 1, label: __("Address Line 1") },

            { fieldtype: "Data", fieldname: "postal_code", label: __("Postal Code") },

            { fieldtype: "Link", fieldname: "address_country", reqd: 1, label: __("Country"), options: "Country" },

            { fieldtype: "Column Break" },

            { fieldtype: "Data", fieldname: "address_line2", label: __("Address Line 2") },

            { fieldtype: "Data", fieldname: "city", reqd: 1, label: __("City / Town") },
        ],
        'primary_action_label': __("Create"),
        'primary_action'(values) {
            // Check Webshop URL → Company required
            if (values.webshop_url && !values.webshop_company) {
                frappe.msgprint(__("Please select a Company when providing a Webshop URL."));
                return;
            }
            frappe.call({
                'method': "microsynth.microsynth.purchasing.create_supplier",
                'args': { 'data': values },
                'freeze': true,
                'freeze_message': __("Creating Supplier ..."),
                'callback': function (r) {
                    if (r.message && r.message.supplier) {
                        frappe.set_route("Form", "Supplier", r.message.supplier);
                        d.hide();
                    }
                }
            });
        }
    });
    d.show();
}
