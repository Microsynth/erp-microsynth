/* Custom script extension for Contact */

// extend/create dashboard
cur_frm.dashboard.add_transactions([
    {
        'label': __("Pre-Sales"),
        'items': ["Quotation"]
    },
    {
        'label': __("Notes"),
        'items': ["Contact Note"]
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
    },
    refresh(frm) {
        // Show buttons if a customer is linked
        if ((frm.doc.links) && (frm.doc.links.length > 0) && (frm.doc.links[0].link_doctype === "Customer")) {

            // Preview Address button
            frm.add_custom_button(__("Preview Address"), function() {
                preview_address(frm, frm.doc.links[0].link_name);
            });

            
            // Button to jump to customer
            frm.add_custom_button(__("Customer"), function() {
                frappe.set_route("Form", "Customer", frm.doc.links[0].link_name);
            });

            frappe.call({
                "method": "frappe.client.get",
                "args": {
                    "doctype": "Customer",
                    "name": frm.doc.links[0].link_name
                },
                "callback": function(response) {
                    var customer = response.message;
                    cur_frm.dashboard.add_comment(__('Customer') + ": " + customer.customer_name, 'blue', true);
                }
            });

            // Quotation button in Create menu
            frm.add_custom_button(__("Quotation"), function() {
                create_quotation(frm);
            }, __("Create"));
            
            // Gecko export button in Create menu
            frm.add_custom_button(__("Gecko Export"), function() {
                frappe.call({
                    "method":"microsynth.microsynth.migration.export_contact_to_gecko",
                    "args": { "contact_name":frm.doc.name }
                });
            }, __("Create"));

            frm.page.set_inner_btn_group_as_primary(__('Create'));
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
                frappe.msgprint(address_layout, __("Address Preview"));
            }
        });
    }
}

function create_quotation(frm){

    frappe.model.open_mapped_doc({
        method: "microsynth.microsynth.quotation.make_quotation",
        args: {contact_name: frm.doc.name },
        frm: frm
    })
}
