// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('Item Price', {
    refresh(frm) {
        if (frm.doc.price_list.includes('Sales Prices')) {
            if (frappe.user.has_role("Sales Manager Extended")) {
                frm.add_custom_button(__("Change reference price"), function() {
                    change_reference_rate();
                });
            } else {
                cur_frm.set_df_property('reference_price_list', 'read_only', true);
                cur_frm.set_df_property('currency', 'read_only', true);
                cur_frm.set_df_property('item_code', 'read_only', true);
                cur_frm.set_df_property('price_list', 'read_only', true);
                cur_frm.set_df_property('min_qty', 'read_only', true);
                cur_frm.set_df_property('valid_from', 'read_only', true);
                cur_frm.set_df_property('valid_upto', 'read_only', true);
            }
            cur_frm.set_df_property('price_list_rate', 'read_only', true);
        }
    }
});


function change_reference_rate(){
    frappe.prompt([
        {'fieldname': 'new_reference_rate', 'fieldtype': 'Float', 'label': __('New Reference Price List Rate'), 'reqd': 1}
    ],
    function(values){
        if (Math.abs(values.new_reference_rate - cur_frm.doc.price_list_rate) < 0.0001) {
            frappe.show_alert('New reference Price List rate equals current reference Price List Rate. No changes applied.');
            return;
        }
        frappe.confirm('Are you sure you want to proceed?<br>All <b>Price Lists</b> referring to this reference Price List "' + cur_frm.doc.price_list + '" <b>will be changed</b> by applying their current discount relative to the current reference price (' + cur_frm.doc.price_list_rate + ' ' + cur_frm.doc.currency + ') to the new reference price (' + values.new_reference_rate + ' ' + cur_frm.doc.currency + ') for item ' + cur_frm.doc.item_code + ': ' + cur_frm.doc.item_name + ' with minimum quantity ' + cur_frm.doc.min_qty +'.<br><br>Please be patient, the process may take several minutes.',
            () => {
                frappe.call({
                    'method': "microsynth.microsynth.pricing.async_change_reference_rate",
                    'args':{
                        'reference_price_list_name': cur_frm.doc.price_list,
                        'item_code': cur_frm.doc.item_code,
                        'min_qty': cur_frm.doc.min_qty,
                        'reference_rate': cur_frm.doc.price_list_rate,
                        'new_reference_rate': values.new_reference_rate,
                        'user': frappe.session.user
                    },
                    'callback': function(r)
                    {
                        setTimeout(function() {cur_frm.refresh();}, 180000);  // reload at least after three minutes
                        // How to show some success message in case everything was fine?
                        // Or is it nearly impossible to get feedback from the enqueued async function?
                    }
                });
            }, () => {
                frappe.show_alert('No new reference Price List rate applied');
            });        
    },
    __('Change reference price'),
    __('OK')
    );
}
