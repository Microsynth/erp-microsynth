/* Custom script extension for Contact */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Selling"),
        'items': ["Quotation"]
    },
    {
        'label': __("Marketing"),
        'items': ["Contact Note", "Benchmark", "Product Idea"]
    }
]);


frappe.ui.form.on('Contact', {
    before_save(frm) {
        update_address_links(frm);

        let first_name = frm.doc.first_name || "";
        let last_name = frm.doc.last_name || "";
        let spacer = "";
        if (frm.doc.last_name) {spacer = " ";}    

        // set full name
        cur_frm.set_value("full_name", (first_name + spacer + last_name));

        // clear routes (to prevent jumping to customer)
        frappe.route_history = [];

        check_email_id(frm);
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
    },
    onload(frm) {
        // Hide dashboard if Contact is versioned
        // Regex: ends with a hyphen followed by 1 or 2 digits
        const pattern = /-\d{1,2}$/;

        if (frm.doc.name && pattern.test(frm.doc.name)) {
            frm.dashboard.hide();
        }
    },
    refresh(frm) {

        // set Contact source
        if (frm.doc.__islocal) {
            cur_frm.set_value("source", "Manual");
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
        if (!frappe.user.has_role("System Manager") && (frm.doc.first_name == "Anonymous" || (frm.doc.source && frm.doc.source == "Punchout"))) {
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

        // show a banner if source = Punchout
        if (frm.doc.source && frm.doc.source == "Punchout") {
            frm.dashboard.add_comment( __("Punchout Contact! Please do <b>not</b> edit."), 'red', true);
        }

        // Show buttons if a customer is linked
        if ((frm.doc.links) && (frm.doc.links.length > 0) && (frm.doc.links[0].link_doctype === "Customer")) {

            // Webshop button
            if (!frm.doc.__islocal && frm.doc.has_webshop_account){
                frm.add_custom_button(__("Webshop"), function() {
                    frappe.call({
                        "method": "microsynth.microsynth.utils.get_webshop_url",
                        "callback": function(response) {
                            var webshop_url = response.message;
                            window.open(webshop_url + "/MasterUser/MasterUser/Impersonate?IdPerson=" + frm.doc.name, "_blank");
                        }
                    });
                });
            }

            // Preview Address button
            frm.add_custom_button(__("Preview Address"), function() {
                preview_address(frm, frm.doc.links[0].link_name);
            });

            // Button to jump to customer
            frm.add_custom_button(__("Customer"), function() {
                frappe.set_route("Form", "Customer", frm.doc.links[0].link_name);
            });

            if (!frm.doc.__islocal && frm.doc.status != "Disabled") {
                // Button to change the customer
                frm.add_custom_button(__("Change Customer"), function() {
                    change_customer(frm);
                });
            }            

            if (frm.doc.status === 'Lead' || frm.doc.contact_classification === 'Lead') {
                var dashboard_comment_color = 'green';
                frm.dashboard.add_comment('This is a lead.', dashboard_comment_color, true);
            } else {
                var dashboard_comment_color = 'blue';
            }

            if (frm.doc.status === 'Open') {
                frappe.call({
                    "method": "microsynth.microsynth.utils.get_potential_contact_duplicates",
                    'args': {
                        'contact_id': frm.doc.name
                    },
                    "callback": function(response) {
                        if (response.message && response.message.length > 0) {
                            if (response.message.length == 1) {
                                frm.dashboard.add_comment('<br>' + response.message.length + ' potential Duplicate:', 'red', true);
                            } else {
                                frm.dashboard.add_comment('<br>' + response.message.length + ' potential Duplicates:', 'red', true);
                            }
                            var contacts = response.message;
                            for (var i = 0; i < contacts.length; i++) {
                                if (i > 10) {
                                    frm.dashboard.add_comment('<b>...</b>', 'red', true);
                                    break;
                                }
                                frm.dashboard.add_comment('<b>' + contacts[i].name + '</b>: ' + contacts[i].first_name + ' ' + (contacts[i].last_name || '') + ', Institute: ' + (contacts[i].institute || '') + ' (<a href="/desk#contact_merger?contact_1=' + frm.doc.name + '&contact_2=' + contacts[i].name + '">Open in Contact Merger</a>)', 'red', true);
                            }
                        }
                    }
                });                
            }

            frappe.call({
                "method": "frappe.client.get",
                "args": {
                    "doctype": "Customer",
                    "name": frm.doc.links[0].link_name
                },
                "callback": function(response) {
                    var customer = response.message;
                    cur_frm.dashboard.add_comment(__('Customer') + ": " + customer.customer_name, dashboard_comment_color, true);
                }
            });

            // Custom email dialog
            frm.add_custom_button(__("Email"), function() {
                open_mail_dialog(frm);
            }, __("Create"));

            // Only show Quotation button if name does not end with a hyphen followed by 1 or 2 digits
            if (!((/-\d{1,2}$/).test(frm.doc.name))) {
                // Quotation button in Create menu
                frm.add_custom_button(__("Quotation"), function() {
                    create_quotation(frm);
                }, __("Create"));
            }

            // Gecko export button in Create menu
            frm.add_custom_button(__("Gecko Export"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.migration.export_contact_to_gecko",
                    "args": { "contact_name":frm.doc.name }
                });
            }, __("Create"));

            frm.page.set_inner_btn_group_as_primary(__('Create'));
        } else if ((frm.doc.links) && (frm.doc.links.length > 0) && (frm.doc.links[0].link_doctype === "Supplier")) {
            // Button to jump to supplier
            frm.add_custom_button(__("Supplier"), function() {
                frappe.set_route("Form", "Supplier", frm.doc.links[0].link_name);
            });

            frappe.call({
                "method": "frappe.client.get",
                "args": {
                    "doctype": "Supplier",
                    "name": frm.doc.links[0].link_name
                },
                "callback": function(response) {
                    var supplier = response.message;
                    cur_frm.dashboard.add_comment(__('Supplier') + ": " + supplier.supplier_name, "blue", true);
                }
            });
        } else {
            cur_frm.dashboard.add_comment(__('Please add a Link to a Customer or Supplier in the Reference section.'), "red", true);
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
                    frappe.msgprint(__('Customer link updated.'));
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
