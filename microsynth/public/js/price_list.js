frappe.ui.form.on('Price List', {
    refresh(frm) {
        if ((frm.doc.name || "").includes("Sales Prices")) {
            frm.remove_custom_button(__("Add / Edit Prices"));
        }

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
    before_save: async function(frm) {
        if (frm.doc.enabled !== 0 || frm.doc.__unsaved !== 1) {
            return;
        }
        const response = await frappe.call({
            "method": "microsynth.microsynth.utils.get_open_documents_for_price_list",
            "args": {
                "price_list_id": frm.doc.name
            },
            "freeze": true,
            "freeze_message": __("Checking open sales documents ...")
        });
        const data = response.message || {};
        let has_open_docs = false;
        let msg = "";

        Object.keys(data).forEach(function(doctype) {
            if (data[doctype].length) {
                has_open_docs = true;
                msg += `<b>${doctype}</b><ul>`;
                data[doctype].forEach(function(document) {
                    msg += `<li>${document.name}</li>`;
                });
                msg += "</ul>";
            }
        });
        if (!has_open_docs) {
            return;
        }

        await new Promise(function(resolve, reject) {
            let choice_made = false;
            const finish = function(keep_enabled) {
                if (choice_made) {
                    return;
                }
                choice_made = true;
                dialog.hide();
                Promise.resolve()
                    .then(() => keep_enabled ? frm.set_value("enabled", 1) : undefined)
                    .then(resolve, reject);
            };
            const dialog = new frappe.ui.Dialog({
                title: __("Keep Price List enabled?"),
                primary_action_label: __("Yes"),
                primary_action: () => finish(true),
                secondary_action_label: __("No"),
                secondary_action: () => finish(false),
                onhide: () => finish(true)
            });
            dialog.$body.append(
                `<p>${__("This Price List is used by open sales documents. Keep it enabled?")}</p>
                <p>${__("Yes: keep enabled. No: disable anyway.")}</p>${msg}`
            );
            dialog.confirm_dialog = true;
            dialog.show();
        });
    }
});
