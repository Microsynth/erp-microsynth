frappe.ui.form.on('Price List', {
    refresh(frm) {
        if (!frm.doc.__islocal && frm.doc.selling) {
            // link to pricing configurator
            frm.add_custom_button(__("Price List"), function() {
                frappe.set_route("query-report", "Pricing Configurator", {'price_list': frm.doc.name});
            });
            // show customers with this price list
            frm.add_custom_button(__("Customers"), function() {
                frappe.set_route("List", "Customer", {"default_price_list": frm.doc.name, "disabled": 0});
            });
            // show Standing Quotations with this price list
            frm.add_custom_button(__("Standing Quotations"), function() {
                frappe.set_route("List", "Standing Quotation", {"price_list": frm.doc.name});
            });
        }
    },
    before_save: function(frm) {
        if (frm._skip_open_doc_check) {
            return;
        }
        // Only act when disabling
        if (frm.doc.enabled === 0 && frm.doc.__unsaved === 1) {
            frappe.call({
                "method": "microsynth.microsynth.utils.get_open_documents_for_price_list",
                "args": {
                    "price_list_id": frm.doc.name
                },
                "freeze": true,
                "freeze_message": "Checking open sales documents ...",
                "callback": function(r) {
                    const data = r.message || {};
                    let has_open_docs = false;
                    let msg = "";

                    Object.keys(data).forEach(function(doctype) {
                        if (data[doctype].length) {
                            has_open_docs = true;
                            msg += `<b>${doctype}</b><ul>`;
                            data[doctype].forEach(function(d) {
                                msg += `<li>${d.name}</li>`;
                            });
                            msg += "</ul>";
                        }
                    });
                    if (has_open_docs) {
                        frappe.validated = false;

                        frappe.confirm(
                            `<p>Do you want to <b>keep</b> this Price List <b>enabled</b>?</p>
                            <p>Click <b>No</b> to disable it anyway (at your <b>own risk</b>).</p>
                            <p>This Price List is used on the following open sales documents:</p>${msg}`
                            ,
                            // NO → disable anyway
                            function() {
                                frm._skip_open_doc_check = true;
                                frappe.validated = true;
                                frm.save();
                            },
                            // YES → keep enabled
                            function() {
                                frm._skip_open_doc_check = true;
                                frm.set_value("enabled", 1);
                                frm.save();
                            }
                        );
                    }
                }
            });
        }
    }
});
