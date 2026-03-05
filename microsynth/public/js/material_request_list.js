// List View customization
frappe.listview_settings['Material Request'] = {
    add_fields: ["material_request_type", "status", "per_ordered", "per_received"],
	get_indicator: function(doc) {
		if(doc.status=="Stopped") {
			return [__("Stopped"), "red", "status,=,Stopped"];
		} else if(doc.docstatus==1 && flt(doc.per_ordered, 2) == 0) {
			return [__("Pending"), "orange", "per_ordered,=,0"];
		}  else if(doc.docstatus==1 && flt(doc.per_ordered, 2) < 100) {
			return [__("Partially ordered"), "yellow", "per_ordered,<,100"];
		} else if(doc.docstatus==1 && flt(doc.per_ordered, 2) == 100) {
			if (doc.material_request_type == "Purchase" && flt(doc.per_received, 2) < 100 && flt(doc.per_received, 2) > 0) {
				return [__("Partially Received"), "yellow", "per_received,<,100"];
			} else if (doc.material_request_type == "Purchase" && flt(doc.per_received, 2) == 100) {
				return [__("Received"), "green", "per_received,=,100"];
			} else if (doc.material_request_type == "Purchase") {
				return [__("Ordered"), "green", "per_ordered,=,100"];
			} else if (doc.material_request_type == "Material Transfer") {
				return [__("Transfered"), "green", "per_ordered,=,100"];
			} else if (doc.material_request_type == "Material Issue") {
				return [__("Issued"), "green", "per_ordered,=,100"];
			} else if (doc.material_request_type == "Customer Provided") {
				return [__("Received"), "green", "per_ordered,=,100"];
			} else if (doc.material_request_type == "Manufacture") {
				return [__("Manufactured"), "green", "per_ordered,=,100"];
			}
		}
	},
    onload: function(listview) {
        add_clear_button();

        // TODO: How to get the following working?
        // // Override the New button action
        // listview.page.set_primary_action(__('New'), function() {
        //     if (!frappe.user.has_role('System Manager')) {
        //         frappe.msgprint({
        //             title: __('Not Allowed'),
        //             indicator: 'red',
        //             message: __('Please use the Button "New Request" in the Material Request Overview report to create a Material Request.')
        //         });
        //         return;
        //     }
        //     frappe.new_doc('Material Request');
        // });
    },
    refresh: function(listview) {
        if (frappe.user.has_role('System Manager')) return;
        // Hide the New button
        listview.page.btn_primary && listview.page.btn_primary.hide();
    }
};
