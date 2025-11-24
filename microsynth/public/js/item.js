/* Custom script extension for Item */

frappe.ui.form.on('Item', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            cur_frm.set_value('is_stock_item', false);
            cur_frm.set_value('include_item_in_manufacturing', false);
        }
        if (frm.doc.__islocal && frm.doc.item_group && frm.doc.item_group == 'Purchasing') {
            cur_frm.set_value('is_stock_item', true);
        }

        // Only show button for Item Group "Purchasing"
        if (frm.doc.item_group === "Purchasing") {
            frm.add_custom_button(__("Add Location"), function () {
                show_add_location_dialog(frm);
            });
        }
    }
});


function show_add_location_dialog(frm) {
    const d = new frappe.ui.Dialog({
        'title': __("Add a Storage Location"),
        'fields': [
            {
                label: __("Subsidiary"),
                fieldname: "subsidiary",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => ({
                    filters: {
                        parent_location: ["in", ["", null]]
                    }
                }),
                default: "Balgach"
            },
            {
                label: __("Floor"),
                fieldname: "floor",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => {
                    return d.get_value("subsidiary")
                        ? { filters: { parent_location: d.get_value("subsidiary") } }
                        : {};
                }
            },
            {
                label: __("Room"),
                fieldname: "room",
                fieldtype: "Link",
                options: "Location",
                reqd: true,
                get_query: () => {
                    return d.get_value("floor")
                        ? { filters: { parent_location: d.get_value("floor") } }
                        : {};
                }
            },
            {
                label: __("Destination"),
                fieldname: "destination",
                fieldtype: "Link",
                options: "Location",
                reqd: false,
                get_query: () => {
                    return d.get_value("room")
                        ? { filters: { parent_location: d.get_value("room") } }
                        : {};
                }
            },
            {
                label: __("Fridge Rack"),
                fieldname: "rack",
                fieldtype: "Link",
                options: "Location",
                reqd: false,
                get_query: () => {
                    return d.get_value("destination")
                        ? { filters: { parent_location: d.get_value("destination") } }
                        : {};
                }
            },
        ],
        'primary_action_label': __("Save"),
        primary_action(values) {
            // Determine the most specific selected location
            let chosen =
                values.rack ||
                values.destination ||
                values.room ||
                values.floor ||
                values.subsidiary;

            if (!chosen) {
                frappe.msgprint(__("No location selected"));
                return;
            }

            frappe.call({
                'method': "microsynth.microsynth.purchasing.add_location_to_item",
                'args': {
                    'item': frm.doc.name,
                    'location': chosen
                },
                'callback': function (r) {
                    if (!r.exc) {
                        frm.reload_doc();
                        d.hide();
                        frappe.msgprint(__("Location added to this item."));
                    }
                }
            });
        }
    });
    d.show();
}
