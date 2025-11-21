/* Custom script extension for Contact */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Selling"),
        'items': ["Quotation", "Credit Account"]
    },
    {
        'label': __("Marketing"),
        'items': ["Contact Note", "Benchmark", "Product Idea"]
    }
]);


let original_customer_link = null;

frappe.ui.form.on('Contact', {
    before_save(frm) {
        const current_customer_link = get_customer_link_from_links(frm.doc.links);

        if (original_customer_link !== current_customer_link) {
            // console.log(`Customer link changed from '${original_customer_link}' to '${current_customer_link}'`);
            update_address_links(frm);
        }

        let first_name = frm.doc.first_name || "";
        let last_name = frm.doc.last_name || "";
        let spacer = "";
        if (frm.doc.last_name) {spacer = " ";}

        // set full name
        cur_frm.set_value("full_name", (first_name + spacer + last_name));

        // clear routes (to prevent jumping to customer)
        frappe.route_history = [];

        check_email_id(frm);

        if (frm.doc.email_ids) {
            // If there is exactly one email_id, set it as is_primary
            if (frm.doc.email_ids.length == 1 && !frm.doc.email_ids.some(e => e.is_primary)) {
                frm.doc.email_ids[0].is_primary = 1;
            }
            // Reminder for primary email
            let emailPrimary = frm.doc.email_ids.filter(e => e.is_primary).length;
            if (emailPrimary !== 1 && frm.doc.email_ids.length > 1) {
                frappe.msgprint(__('Please select exactly one primary Email.'));
            }
        }
        if (frm.doc.phone_nos) {
            if (frm.doc.phone_nos.length == 1 && !frm.doc.phone_nos.some(p => p.is_primary_phone) && !frm.doc.phone_nos[0].is_primary_mobile_no) {
                frm.doc.phone_nos[0].is_primary_phone = 1;
            }
            let phonePrimary = frm.doc.phone_nos.filter(p => p.is_primary_phone).length;
            if (phonePrimary !== 1 && frm.doc.phone_nos.length > 1) {
                frappe.msgprint(__('Please select exactly one primary Phone Number.'));
            }
        }
    },
    validate(frm) {
        if (frm.doc.salutation && !['Frau', 'Herr', 'Ms.', 'Mr.', 'Mme', 'M.'].includes(frm.doc.salutation)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'red',
                message: __("Please set the field <b>Salutation</b> to a valid value (Frau / Herr / Ms. / Mr. / Mme / M.).")
            });
            frappe.validated=false;
        }
        if (frm.doc.designation && frm.doc.has_webshop_account && !['Dr.', 'Prof.', 'Prof. Dr.'].includes(frm.doc.designation)) {
            frappe.msgprint({
                title: __('Validation'),
                indicator: 'red',
                message: __("Please set the field <b>Title</b> to a valid value (Dr. / Prof. / Prof. Dr.) or leave it empty.")
            });
            frappe.validated=false;
        }
    },
    onload(frm) {
        // Hide dashboard if Contact is versioned
        // Regex: ends with a hyphen followed by 1 or 2 digits
        const pattern = /-\d{1,2}$/;

        if (frm.doc.name && pattern.test(frm.doc.name)) {
            frm.dashboard.hide();
        }

        // Store the original customer link (if any)
        original_customer_link = get_customer_link_from_links(frm.doc.links);
    },
    refresh(frm) {
        const link = frm.doc.links?.[0];
        const link_name = link?.link_name;
        const is_customer = link.link_doctype === "Customer";
        const is_supplier = link.link_doctype === "Supplier";

        frm.dashboard.clear_comment();

        // set Contact source
        if (frm.doc.__islocal) {
            cur_frm.set_value("contact_source", "Manual");
            cur_frm.set_value("has_webshop_account", 0);
        }

        // lock Links table of webshop account contacts
        if (!frm.doc.__islocal && frm.doc.has_webshop_account) {
            cur_frm.set_df_property('links', 'read_only', true);
            cur_frm.get_field("links").grid.fields_map['link_doctype'].read_only = 1;
            cur_frm.get_field("links").grid.fields_map['link_name'].read_only = 1;
        }

        // remove Menu > Email
        var target ="span[data-label='" + __("Email") + "']";
        $(target).parent().parent().remove();
        frappe.ui.keys.off("ctrl+e");                                   // and disable keyboard shortcut

        // remove 'Invite as User' button from ERPNext
        $("button[data-label='" + encodeURI(__("Invite as User")) + "']").remove();

        // lock all fields except Institute Key, Group Leader, Cost Center if First Name = "Anonymous" or if source = Punchout
        if (!frappe.user.has_role("System Manager") && (frm.doc.first_name == "Anonymous" || (frm.doc.contact_source && frm.doc.contact_source == "Punchout"))) {
            cur_frm.set_df_property('first_name', 'read_only', true);
            cur_frm.set_df_property('middle_name', 'read_only', true);
            cur_frm.set_df_property('last_name', 'read_only', true);
            cur_frm.set_df_property('user', 'read_only', true);
            cur_frm.set_df_property('address', 'read_only', true);
            cur_frm.set_df_property('status', 'read_only', true);
            cur_frm.set_df_property('salutation', 'read_only', true);
            cur_frm.set_df_property('designation', 'read_only', true);
            cur_frm.set_df_property('gender', 'read_only', true);
            cur_frm.set_df_property('email_ids', 'read_only', true);
            cur_frm.set_df_property('phone_nos', 'read_only', true);
            cur_frm.set_df_property('is_primary_contact', 'read_only', true);
            cur_frm.set_df_property('links', 'read_only', true);
            cur_frm.set_df_property('institute', 'read_only', true);
            cur_frm.set_df_property('department', 'read_only', true);
            cur_frm.set_df_property('room', 'read_only', true);
            cur_frm.set_df_property('unsubscribed', 'read_only', true);
            cur_frm.set_df_property('interests', 'read_only', true);
            cur_frm.set_df_property('punchout_identifier', 'read_only', true);
            cur_frm.set_df_property('punchout_shop', 'read_only', true);
            cur_frm.set_df_property('receive_newsletter', 'read_only', true);
            cur_frm.set_df_property('subscribe_date', 'read_only', true);
            cur_frm.set_df_property('unsubscribe_date', 'read_only', true);
        }

        // lock email_ids if has_webshop_account == 1
        if (frm.doc.has_webshop_account && frm.doc.email_ids && frm.doc.email_ids.length > 0 && !frappe.user.has_role("System Manager")) {
            cur_frm.get_field("email_ids").grid.fields_map['email_id'].read_only = 1;
            cur_frm.get_field("email_ids").grid.fields_map['is_primary'].read_only = 1;
            frm.dashboard.add_comment('This Contact has a Webshop Account: Changes should be made there.', 'orange', true);
        }

        // show a banner if source = Punchout
        if (frm.doc.contact_source && frm.doc.contact_source == "Punchout") {
            frm.dashboard.add_comment( __("Punchout Contact! Please do <b>not</b> edit."), 'red', true);
        }

        // Show buttons if a customer is linked
        if (is_customer && link_name) {

            // Webshop button
            if (!frm.doc.__islocal && frm.doc.has_webshop_account && frm.doc.status === "Passive") {
                frm.add_custom_button(__("Webshop"), function () {
                    frappe.call({
                        "method": "microsynth.microsynth.utils.get_webshop_url",
                        "callback": function (response) {
                            const webshop_url = response.message;
                            if (webshop_url) {
                                window.open(`${webshop_url}/MasterUser/MasterUser/Impersonate?IdPerson=${frm.doc.name}`, "_blank");
                            }
                        }
                    });
                });
            }

            // Preview Address button
            frm.add_custom_button(__("Preview Address"), function () {
                preview_address(frm, link_name);
            });

            // Button to jump to Customer
            frm.add_custom_button(__("Customer"), function () {
                frappe.set_route("Form", "Customer", link_name);
            });

            // Button to change the Customer
            if (!frm.doc.__islocal && frm.doc.status !== "Disabled" && frm.doc.contact_source !== "Punchout") {
                frm.add_custom_button(__("Change Customer"), function () {
                    change_customer(frm);
                });
            }

            // Show buttons if a customer is linked
            if (is_customer && link_name) {
                if (!frm.doc.__islocal && frm.doc.has_webshop_account && frm.doc.status === "Passive") {
                    frm.add_custom_button(__("Price List PDF"), function () {
                        const encodedContact = encodeURIComponent(frm.doc.name);
                        const url = frappe.urllib.get_full_url(
                            "/api/method/microsynth.microsynth.webshop.prepare_price_list_pdf_download?contact=" + encodedContact
                        );
                        const w = window.open(url);
                        if (!w) {
                            frappe.msgprint(__("Please enable pop-ups"));
                        }
                    }, __("Create"));
                }
            }

            // Show lead classification comment
            if (frm.doc.status === 'Lead' || frm.doc.contact_classification === 'Lead') {
                frm.dashboard.add_comment('This is a lead.', 'green', true);
            }

            // Show potential duplicates immediately (do not defer to a button)
            if (!frm.doc.__islocal && frm.doc.status === 'Open' && frm.doc.has_webshop_account) {  // only Webshop Contacts are Open, therefore use has_webshop_account to only show duplicates on a shipping Co0ntact
                frappe.call({
                    "method": "microsynth.microsynth.utils.get_potential_contact_duplicates",
                    'args': {
                        'contact_id': frm.doc.name
                    },
                    callback: function (response) {
                        const contacts = response.message || [];
                        if (contacts.length > 0) {
                            const label = contacts.length === 1 ? "potential Duplicate:" : "potential Duplicates:";
                            let html = `<br>${contacts.length} ${label}<br>`;
                            contacts.slice(0, 10).forEach(c => {
                                html += `<b>${c.name}</b>: ${c.first_name} ${c.last_name || ''}, Institute: ${c.institute || ''} (<a href="/desk#contact_merger?contact_1=${frm.doc.name}&contact_2=${c.name}">Open in Contact Merger</a>)<br>`;
                            });
                            if (contacts.length > 10) {
                                html += "<b>...</b><br>";
                            }
                            frm.dashboard.add_comment(html, 'red', true);
                        }
                    }
                });
            }

            // Get and show Customer Name
            frappe.call({
                "method": "frappe.client.get_value",
                "args": {
                    "doctype": "Customer",
                    "filters": { name: link_name },
                    "fieldname": "customer_name"
                },
                "callback": function(response) {
                    const customer_name = response.message?.customer_name;
                    if (customer_name) {
                        frm.dashboard.add_comment("Customer: " + customer_name, "blue", true);
                    }
                }
            });

            // Custom email dialog
            frm.add_custom_button(__("Email"), function () {
                open_mail_dialog(frm);
            }, __("Create"));

            // Only show Quotation button if name does not end with a hyphen followed by 1 or 2 digits
            if (!(/-\d{1,2}$/).test(frm.doc.name)) {
                // Quotation button in Create menu
                frm.add_custom_button(__("Quotation"), function () {
                    create_quotation(frm);
                }, __("Create"));
            }

            // Button to create promotion credit
            if (!frm.doc.__islocal && frm.doc.status !== "Disabled" && frm.doc.has_webshop_account && frappe.user.has_role("Sales Manager")) {
                frm.add_custom_button(__("Promotion Credits"), function () {
                    create_promotion_credits(frm);
                }, __("Create"));
            }

            // Gecko export button in Create menu
            frm.add_custom_button(__("Gecko Export"), function () {
                frappe.call({
                    "method": "microsynth.microsynth.migration.export_contact_to_gecko",
                    "args": { "contact_name": frm.doc.name }
                });
            }, __("Create"));

            frm.page.set_inner_btn_group_as_primary(__('Create'));

        } else if (is_supplier && link_name) {
            // Button to jump to Supplier
            frm.add_custom_button(__("Supplier"), function () {
                frappe.set_route("Form", "Supplier", link_name);
            });

            // Get and show Supplier Name
            frappe.call({
                "method": "frappe.client.get_value",
                "args": {
                    "doctype": "Supplier",
                    "filters": { "name": link_name },
                    "fieldname": "supplier_name"
                },
                callback: function(response) {
                    const supplier_name = response.message?.supplier_name;
                    if (supplier_name) {
                        frm.dashboard.add_comment("Supplier: " + supplier_name, "blue", true);
                    }
                }
            });

        } else {
            // No Customer or Supplier link
            frm.dashboard.add_comment(__('Please add a Link to a Customer or Supplier in the Reference section.'), "red", true);
        }
    }
});


function update_address_links(frm) {
    if (frm.doc.address) {
        frappe.call({
            "method":"microsynth.microsynth.utils.update_address_links_from_contact",
            "args":{
                "address_name":frm.doc.address,
                "links": (frm.doc.links || [] )
            }
        })
    }
}


function create_promotion_credits(frm) {
    // --- 1. Determine the Customer linked to this Contact ---
    let customer_id = null;
    if (frm.doc.links && frm.doc.links.length) {
        for (let l of frm.doc.links) {
            if (l.link_doctype === "Customer") {
                customer_id = l.link_name;
                break;
            }
        }
    }
    if (!customer_id) {
        frappe.msgprint(__("This Contact is not linked to any Customer."));
        return;
    }

    // --- 2. Fetch Customer defaults (default_company, default_currency) ---
    frappe.call({
        'method': "frappe.client.get",
        'args': {
            'doctype': "Customer",
            'name': customer_id
        },
        'callback': function (r) {
            if (r.exc || !r.message) {
                frappe.msgprint(__("Could not load Customer data."));
                return;
            }

            let customer = r.message;

            let default_company = customer.default_company || "";
            let default_currency = customer.default_currency || "";

            // --- 3. Build dialog ---
            frappe.model.with_doctype("Product Type Link", function() {
                let d = new frappe.ui.Dialog({
                    'title': __("Create Promotion Credits"),
                    'fields': [
                        {
                            label: __("Account Title"),
                            fieldname: "account_name",
                            fieldtype: "Data",
                            reqd: 1
                        },
                        {
                            label: __("Company"),
                            fieldname: "company",
                            fieldtype: "Link",
                            options: "Company",
                            reqd: 1,
                            default: default_company
                        },
                        {
                            'fieldtype': 'Table MultiSelect',
                            'fieldname': 'product_types',
                            'label': __("Product Types"),
                            'reqd': 1,
                            'options': 'Product Type Link'
                        },
                        {
                            label: __("Amount"),
                            fieldname: "amount",
                            fieldtype: "Currency",
                            reqd: 1
                        },
                        {
                            label: __("Currency"),
                            fieldname: "currency",
                            fieldtype: "Link",
                            options: "Currency",
                            reqd: 1,
                            read_only: 1,
                            default: default_currency
                        },
                        {
                            label: __("Expiry Date"),
                            fieldname: "expiry_date",
                            fieldtype: "Date",
                            reqd: 1
                        },
                        {
                            label: __("Override Item Name"),
                            fieldname: "override_item_name",
                            fieldtype: "Data",
                            reqd: 0
                        },
                        {
                            label: __("Description"),
                            fieldname: "description",
                            fieldtype: "Small Text",
                            reqd: 0
                        }
                    ],
                    'primary_action_label': __("Create"),
                    'primary_action'(values) {
                        d.hide();                                       // hide the dialog first - then freeze is visible
                        // --- 4. Validate required fields ---
                        if (!values.account_name ||
                            !values.company ||
                            !values.product_types ||
                            !values.amount ||
                            !values.currency ||
                            !values.expiry_date) {
                            frappe.msgprint(__("Please fill all mandatory fields."));
                            return;
                        }
                        let raw = values.product_types || [];
                        let product_types = [];

                        if (Array.isArray(raw)) {
                            raw.forEach(function(r) {
                                if (r && r.product_type) {
                                    product_types.push(r.product_type);
                                } else if (typeof r === "string") {
                                    product_types.push(r);
                                }
                            });
                        }

                        // --- 5. Call backend to create credit account + SI ---
                        frappe.call({
                            'method': "microsynth.microsynth.credits.create_promotion_credit_account",
                            'args': {
                                'account_name': values.account_name,
                                'customer_id': customer_id,
                                'company': values.company,
                                'webshop_account': frm.doc.name,  // Contact ID
                                'currency': values.currency,
                                'product_types': product_types,
                                'expiry_date': values.expiry_date,
                                'description': values.description || "",
                                'amount': values.amount,
                                'override_item_name': values.override_item_name || null
                            },
                            'freeze': true,
                            'freeze_message': __("Creating Promotion Credits..."),
                            'callback': function (r) {
                                if (r.exc) return;
                                let si = r.message;
                                if (si) {
                                    frappe.show_alert(__("Promotion Credits created"));
                                    frappe.set_route("Form", "Sales Invoice", si);
                                }
                            }
                        });
                        return;
                    },
                    'secondary_action_label': __("Close"),
                    'secondary_action'() {
                        return;
                    }
                });
                d.show();
            });
        }
    });
}


function change_customer(frm) {
    if (frm.doc.links.length !== 1) {
        frappe.msgprint(__('This action is only allowed when there is exactly one Customer linked. Please contact IT App.'));
        return;
    }
    frappe.prompt([
        {
            'fieldname': 'new_customer',
            'label': 'New Customer',
            'fieldtype': 'Link',
            'options': 'Customer',
            'reqd': 1
        }
    ],
    function (values) {
        frappe.call({
            method: 'microsynth.microsynth.webshop.change_contact_customer',
            args: {
                'contact_id': frm.doc.name,
                'new_customer_id': values.new_customer
            },
            callback: function (r) {
                if (!r.exc) {
                    //frappe.msgprint(__('Customer link updated.'));
                    frm.reload_doc();
                }
            }
        });
    },
    __('Change Customer'),
    __('Change'));
}


function check_email_id(frm) {
    if (!frm.doc.email_id && frm.doc.email_ids && frm.doc.email_ids.length > 0) {
        var is_primary = false;
        for (var i = 0; i < frm.doc.email_ids.length; i++) {
            is_primary = (frm.doc.email_ids[i].is_primary == 1) || is_primary;
        }
        if (!is_primary){
            frappe.msgprint({
                title: __('Missing Email Address'),
                indicator: 'orange',
                message: "Please tick exactly one Email ID as 'Is Primary'."
            });
        }
    }
}


function preview_address(frm, customer) {
    if (!frm.doc.address) {
        frappe.msgprint(__("No address defined"), __("Address Preview"));
    } else if (frm.doc.__islocal) {
        frappe.msgprint(__("Please save first"), __("Address Preview"));
    } else if (!customer) {
        frappe.msgprint(__("No customer defined"), __("Address Preview"));
    } else {
        frappe.call({
            "method": "microsynth.microsynth.utils.get_print_address",
            "args": {
                "contact": frm.doc.name,
                "address": frm.doc.address,
                "customer": customer
            },
            "callback": function(response) {
                var address_layout = response.message;
                console.log(address_layout);
                var d = new frappe.ui.Dialog({
                    'fields': [
                        {'fieldname': 'address_preview', 'fieldtype': 'Data', 'read_only': 1, 'default': address_layout}
                    ],
                    'primary_action': function(){
                        //var values = d.get_values();
                        frappe.call({
                            "method": "microsynth.microsynth.labels.print_contact_shipping_label",
                            "args": {
                                "address_id": frm.doc.address,
                                "contact_id": frm.doc.name,
                                "customer_id": customer
                            },
                            'callback': function(r) {
                                d.hide();
                                frappe.show_alert( __("Adress Label printed.") );
                            }
                        });
                    },
                    'primary_action_label': __('Print Label'),
                    'title': __('Address Preview')
                });
                d.show();
            }
        });
    }
}


function create_quotation(frm){
    frappe.model.open_mapped_doc({
        method: "microsynth.microsynth.quotation.make_quotation",
        args: {contact_name: frm.doc.name},
        frm: frm
    })
}


function open_mail_dialog(frm){
    new frappe.erpnextswiss.MailComposer({
        doc: cur_frm.doc,
        frm: cur_frm,
        subject: "",
        recipients: frm.doc.email_id,
        cc: "info@microsynth.ch",
        attach_document_print: false,
        txt: "",
        check_all_attachments: false
    });
}


// Helper function to extract customer link name from links table
function get_customer_link_from_links(links) {
    const customer_link = (links || []).find(link => link.link_doctype === 'Customer');
    return customer_link ? customer_link.link_name : null;
}
