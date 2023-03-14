/* common functions */


// naming series automation
function prepare_naming_series(frm) {
    locals.naming_series_map = null;
    // cache naming series
    frappe.call({
        'method': 'microsynth.microsynth.naming_series.get_naming_series',
        'args': {
            'doctype': (frm.doc.doctype === "Sales Invoice" && frm.doc.is_return === 1) ? "Credit Note" : frm.doc.doctype
        },
        'callback': function (r) {
            locals.naming_series_map = r.message;
        }
    });
    if (!frm.doc.__islocal) {
        // lock company on saved records (prevent change due to naming series)
        cur_frm.set_df_property('company', 'read_only', 1);
    }
}

function set_naming_series(frm) {
    if (locals.naming_series_map) {
        cur_frm.set_value("naming_series", locals.naming_series_map[frm.doc.company]);
    } else {
        setTimeout(() => { set_naming_series(frm); }, 1000);
    }
}

// mark navbar in specific colour
window.onload = async function () {
    await sleep(1000);
    var navbars = document.getElementsByClassName("navbar");
    if (navbars.length > 0) {
        if (window.location.hostname.includes("erp-test") || (window.location.hostname.includes("localhost"))) {
            navbars[0].style.backgroundColor = "#e65023";
        }
    }
}

function sleep(milliseconds) {
   return new Promise(resolve => setTimeout(resolve, milliseconds));
}

// Set the taxes from the tax template 
function update_taxes(company, customer, address, category) {   
    frappe.call({
        "method": "microsynth.microsynth.utils.find_tax_template",
        "args": {
            "company": company,
            "customer": customer,
            "shipping_address": address,
            "category": category 
        },
        "async": false,
        "callback": function(response){
            var taxes = response.message;   
            
            cur_frm.set_value("taxes_and_charges", taxes);

            frappe.call({
                "method":"frappe.client.get",
                "args": {
                    "doctype": "Sales Taxes and Charges Template",
                    "name": taxes
                },
                "async": false,
                "callback": function(response){
                    var tax_template = response.message;
                    cur_frm.clear_table("taxes");
                    for (var t = 0; t < tax_template.taxes.length; t++) {
                        var child = cur_frm.add_child('taxes')
                        
                        frappe.model.set_value(child.doctype, child.name, 'charge_type', tax_template.taxes[t].charge_type);
                        frappe.model.set_value(child.doctype, child.name, 'account_head', tax_template.taxes[t].account_head);
                        frappe.model.set_value(child.doctype, child.name, 'description', tax_template.taxes[t].description);
                        frappe.model.set_value(child.doctype, child.name, 'cost_center', tax_template.taxes[t].cost_center);
                        frappe.model.set_value(child.doctype, child.name, 'rate', tax_template.taxes[t].rate);
                    }
                }
            });
        }
    });
}

