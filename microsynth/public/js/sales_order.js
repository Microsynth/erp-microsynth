/* Custom script extension for Sales Order */

locals.naming_series_map = null;

frappe.ui.form.on('Sales Order', {
    refresh(frm) {
		// cache naming series
		frappe.call({
			'method': 'microsynth.microsynth.naming_series.get_naming_series',
			'args': {
				'doctype': 'Sales Order'
			},
			'callback': function (r) {
				locals.naming_series_map = r.message;
			}
		});
		if (!frm.doc.__islocal) {
			// lock company on saved records (prevent change due to naming series)
			cur_frm.set_df_property('company', 'read_only', 1);
		}
	},
    company(frm) {
		// set naming series
		set_naming_series(frm);
    }
});

frappe.ui.form.on('Sales Order Item', {
    qty(frm, cdt, cdn) {
        fetch_price_list_rate(frm, cdt, cdn);
    }
});

function set_naming_series(frm) {
	if (locals.naming_series_map) {
		cur_frm.set_value("naming_series", locals.naming_series_map[frm.doc.company]);
	} else {
		setTimeout(() => { set_naming_series(frm); }, 1000);
	}
}
