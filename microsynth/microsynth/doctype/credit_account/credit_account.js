// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Credit Account', {
    refresh: function(frm) {
        // Add Overview button to get to Customer Credits report
        frm.add_custom_button(__('Overview'), function() {
            frappe.set_route('query-report', 'Customer Credits', {
                customer: frm.doc.customer,
                company: frm.doc.company,
                credit_account: frm.doc.name
            });
        });
        // Make fields read-only if there are transactions
        if (!frm.doc.__islocal && frm.doc.has_transactions) {
            cur_frm.set_df_property('customer', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('currency', 'read_only', true);
            cur_frm.set_df_property('account_type', 'read_only', true);
        }
        // Render dashboard
        if (!frm.doc.__islocal) {
            frm.trigger('render_dashboard');
        }
    },
    render_dashboard(frm) {
        frappe.call({
            method: 'microsynth.microsynth.doctype.credit_account.credit_account.get_dashboard_data',
            args: { credit_account: frm.doc.name },
            callback: function(r) {
                if (!r.message) return;
                const html = frm.events.make_dashboard_html(frm, r.message);
                frm.fields_dict.overview.$wrapper.html(html);
            }
        });
    },

    make_dashboard_html(frm, data) {
        const make_table = (label, items, doctype) => {
            if (!items.length) return '';
            const rows = items.map(i => `
                <tr>
                    <td><a href="/app/${frappe.scrub(doctype)}/${i.name}" target="_blank">${i.name}</a></td>
                    <td>${frappe.datetime.str_to_user(i.transaction_date || i.posting_date || '')}</td>
                    <td>${i.customer_name || i.customer || ''}</td>
                    <td style="text-align:right;">${format_currency(i.grand_total, i.currency)}</td>
                </tr>`).join('');
            return `
                <div class="dashboard-section">
                    <h5>${__(label)}</h5>
                    <table class="table table-sm table-bordered" style="margin-bottom:10px;">
                        <thead>
                            <tr><th>${__('Name')}</th><th>${__('Date')}</th><th>${__('Customer')}</th><th>${__('Total')}</th></tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>`;
        };
        return `
            <div class="credit-account-dashboard">
                ${make_table('Sales Orders', data.sales_orders, 'Sales Order')}
                ${make_table('Sales Invoices', data.sales_invoices, 'Sales Invoice')}
            </div>`;
    }
});
