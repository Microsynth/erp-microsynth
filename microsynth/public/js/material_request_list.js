// List View customization
frappe.listview_settings['Material Request'] = {
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
    }
};
