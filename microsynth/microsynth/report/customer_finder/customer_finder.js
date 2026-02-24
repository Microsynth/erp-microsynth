// Copyright (c) 2022, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Finder"] = {
    "filters": [
        {
            "fieldname": "contact_name",
            "label": __("Person ID"),
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "contact_full_name",
            "label": __("Contact Name"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_email",
            "label": __("Contact Email"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "customer",
            "label": __("Customer (Company/Uni)"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "customer_id",
            "label": __("Customer ID"),
            "fieldtype": "Data",
            "options": "",
            "hidden": 1
        },
        {
            "fieldname": "contact_institute",
            "label": __("Institute"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_institute_key",
            "label": __("Institute Key"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_department",
            "label": __("Department"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_group_leader",
            "label": __("Group Leader"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "address_country",
            "label": __("Country"),
            "fieldtype": "Link",
            "options": "Country"
        },
        {
            "fieldname": "address_city",
            "label": __("City"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "address_street",
            "label": __("Street"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "price_list",
            "label": __("Price List"),
            "fieldtype": "Link",
            "options": "Price List"
        },
        {
            "fieldname": "account_manager",
            "label": __("Sales Manager"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "tax_id",
            "label": __("Tax ID"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_status",
            "label": __("Contact Status"),
            "fieldtype": "Select",
            "options": [ '', 'Passive', 'Open', 'Lead', 'Replied', 'Disabled']
        },
        {
            "fieldname": "contact_classification",
            "label": __("Contact Classification"),
            "fieldtype": "Select",
            "options": [ '', 'Buyer', 'Former Buyer', 'Lead']
        },
        {
            "fieldname": "customer_status",
            "label": __("Customer Status"),
            "fieldtype": "Select",
            "options": [ '', 'active', 'former', 'potential']
        },
        {
            "fieldname":"include_disabled",
            "label": __("Include disabled Customers (e.g. leads)"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
        var btn = report.page.add_inner_button(__('New Lead'), function () {
            open_new_lead_dialog();
        });
        btn.addClass('btn-success');
    },
    'after_datatable_render': function(report) {
        const applyRowColors = () => {
            const rows = document.querySelectorAll('[data-row-index]');
            rows.forEach(row => {
                const index = parseInt(row.getAttribute('data-row-index'), 10);
                const rowData = frappe.query_report.data[index];
                if (!rowData) return;
                const highlight = rowData.has_webshop_account ? '#E6FFE6' : '';
                row.style.backgroundColor = highlight;
            });
        };
        applyRowColors();  // Initial run after render

        // Add MutationObserver only once
        const scrollArea = document.querySelector('.dt-scrollable');
        if (scrollArea && !scrollArea._observerAttached) {
            const observer = new MutationObserver(() => {
                applyRowColors();  // Reapply styles on changes
            });
            observer.observe(scrollArea, {
                childList: true,
                subtree: true,
            });
            scrollArea._observerAttached = true;
        }
    }
};


function open_new_lead_dialog() {
    const today = frappe.datetime.get_today();
    const d = new frappe.ui.Dialog({
        'title': __("Create a new Lead (Customer, Contact, Address, Contact Note)"),
        'fields': [
            // Section 1: Customer
            { fieldtype: "Section Break" },
            { fieldtype: "Link", fieldname: "existing_customer", label: __("Existing Customer"), options: "Customer",
                get_query: function() {
                    return {
                        'filters': {
                            'disabled': ["!=", 1],
                            'is_internal_customer': 0
                        }
                    };
                },
                change: function() { fetch_customer_fields(d); } },
            { fieldtype: "Link", fieldname: "account_manager", label: __("Sales Manager"), options: "User", reqd: 1 },
            { fieldtype: "Link", fieldname: "default_currency", label: __("Billing Currency"), options: "Currency", reqd: 1 },
            { fieldtype: "Column Break" },
            { fieldtype: "Data", fieldname: "customer_name", label: __("Full Customer Name"), reqd: 1 },
            { fieldtype: "Link", fieldname: "territory", label: __("Territory"), options: "Territory", reqd: 1,
                get_query: function() {
                    return {
                        'filters': {
                            'is_group': 0,
                            'name': ["not in", ["All Territories", "Rest of the World", "Rest of Europe"]]
                        }
                    };
                }
             },
            { fieldtype: "Link", fieldname: "default_price_list", label: __("Default Price List"), options: "Price List", reqd: 1,
                get_query: function() {
                    return {
                        'filters': {
                            'enabled': 1,
                        }
                    };
                }
             },
            { fieldtype: "Column Break" },
            { fieldtype: "Link", fieldname: "company", label: __("Default Company"), options: "Company", reqd: 1 },
            { fieldtype: "Select", fieldname: "language", label: __("Print Language"), options: "en\nde\nfr", reqd: 1, default: "en" },

            // Section 2: Contact
            { fieldtype: "Section Break" },
            { fieldtype: "Data", fieldname: "first_name", label: __("First Name"), reqd: 1 },
            { fieldtype: "Select", fieldname: "salutation", label: __("Salutation (Ms. / Mr.)"), options: "\nMs.\nMr." },
            { fieldtype: "Column Break" },
            { fieldtype: "Data", fieldname: "last_name", label: __("Last Name") },
            { fieldtype: "Select", fieldname: "title", label: __("Title (Dr. / Prof. / Prof. Dr.)"), options: "\nDr.\nProf.\nProf. Dr." },
            { fieldtype: "Column Break" },
            { fieldtype: "Data", fieldname: "email", label: __("Email Address") },
            { fieldtype: "Data", fieldname: "phone", label: __("Phone") },

            // Section 3: Address
            { fieldtype: "Section Break" },
            { fieldtype: "Data", fieldname: "address_line1", label: __("Address Line 1"), reqd: 1 },
            { fieldtype: "Data", fieldname: "address_line2", label: __("Address Line 2") },
            { fieldtype: "Column Break" },
            { fieldtype: "Data", fieldname: "postal_code", label: __("Postal Code"), reqd: 1 },
            { fieldtype: "Data", fieldname: "city", label: __("City/Town"), reqd: 1 },
            { fieldtype: "Column Break" },
            { fieldtype: "Data", fieldname: "state", label: __("State") },
            { fieldtype: "Link", fieldname: "country", label: __("Country"), options: "Country", reqd: 1 },

            // Section 4: Contact Note
            { fieldtype: "Section Break" },
            { fieldtype: "Date", fieldname: "note_date", label: __("Date"), default: today },
            { fieldtype: "Column Break" },
            { fieldtype: "Select", fieldname: "contact_note_type", label: __("Contact Note Type"), options: "\nEmail\nVisit\nPhone\nVideo Call\nConference\nMarketing\nOther" },
            { fieldtype: "Column Break" },
            { fieldtype: "Small Text", fieldname: "note", label: __("Note") },
        ],
        'primary_action_label': __("Create"),
        primary_action(values) {
            // Validate Contact Note fields
            if (values.note && (!values.note_date || !values.contact_note_type)) {
                frappe.msgprint(__("If Note is filled, Date and Contact Note Type are required."));
                return;
            }
            frappe.call({
                'method': "microsynth.microsynth.marketing.create_lead_with_contact_address_note",
                'args': { 'data': values },
                'freeze': true,
                'freeze_message': __("Creating Lead ..."),
                'callback': function(r) {
                    if (r.message && r.message.customer) {
                        frappe.set_route("Form", "Customer", r.message.customer);
                    }
                }
            });
            d.hide();
        }
    });
    d.show();

    // Force wider dialog
    setTimeout(() => {
        let modals = document.getElementsByClassName('modal-dialog');
        if (modals.length > 0) {
            modals[modals.length - 1].style.width = '900px';
        }
    }, 300);
}

function fetch_customer_fields(dialog) {
    const customer = dialog.get_value("existing_customer");
    if (!customer) return;
    frappe.call({
        'method': "frappe.client.get",
        'args': {
            'doctype': "Customer",
            'name': customer
        },
        'callback': function(r) {
            if (r.message) {
                dialog.set_value("customer_name", r.message.customer_name);
                dialog.set_value("company", r.message.default_company);
                dialog.set_value("account_manager", r.message.account_manager);
                dialog.set_value("territory", r.message.territory);
                dialog.set_value("default_currency", r.message.default_currency);
                dialog.set_value("default_price_list", r.message.default_price_list);
                dialog.set_value("language", r.message.language || "en");
            }
        }
    });
}
