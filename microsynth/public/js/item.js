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

        if (frm.doc.storage_locations.length > 0) {
            // Remove previous dashboard comments
            frm.dashboard.clear_comment();

            // Collect all location paths
            const storage_locations = frm.doc.storage_locations || [];

            if (!storage_locations.length) return;

            const location_promises = storage_locations.map(row => {
                return frappe.call({
                    method: "microsynth.microsynth.purchasing.get_location_path_string",
                    args: { location_name: row.location },
                });
            });

            // Wait for all calls to finish
            Promise.all(location_promises).then(results => {
                const paths = results
                    .map(r => r.message)
                    .filter(p => p); // remove empty

                if (!paths.length) return;

                const text = "<b>Storage Locations:</b><br>" + paths.join("<br>");

                // Add permanent green dashboard comment
                frm.dashboard.add_comment(text, 'green', true);
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
                default: "Balgach",
                onchange: () => {
                    // Auto-clear dependents
                    d.set_value("floor", "");
                    d.set_value("room", "");
                    d.set_value("destination", "");
                    d.set_value("rack", "");
                    refresh_field_states(d);
                }
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
                },
                onchange: () => {
                    d.set_value("room", "");
                    d.set_value("destination", "");
                    d.set_value("rack", "");
                    refresh_field_states(d);
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
                },
                onchange: () => {
                    d.set_value("destination", "");
                    d.set_value("rack", "");
                    refresh_field_states(d);
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
                },
                onchange: () => {
                    d.set_value("rack", "");
                    refresh_field_states(d);
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

    // Initialize states: disable child fields at start
    refresh_field_states(d);
}


function refresh_field_states(d) {
    // Retrieve values
    const subsidiary = d.get_value("subsidiary");
    const floor = d.get_value("floor");
    const room = d.get_value("room");
    const destination = d.get_value("destination");

    // Enable/disable based on hierarchy
    d.get_field("floor").df.read_only = !subsidiary;
    d.get_field("room").df.read_only = !floor;
    d.get_field("destination").df.read_only = !room;
    d.get_field("rack").df.read_only = !destination;

    d.refresh();
}
