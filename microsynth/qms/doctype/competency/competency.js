// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('Competency', {
    setup: function(frm) {
        frm.fields_dict.qm_documents.grid.get_field('qm_document').get_query = function() {
            return {
                filters: [
                    ['status', '=', 'Valid']
                ]
            };
        };
    },

    refresh: function(frm) {
        hide_staff_profile_add_button(frm);
        update_staff_profile_dashboard(frm);

        // if (frm.doc.docstatus === 1 && frm.doc.status === "Valid") {
        // 	frm.add_custom_button(__('New Version'), function() {
        // 		create_new_version(frm);
        // 	}, __('Create'));
        // }
    }
});


function hide_staff_profile_add_button(frm) {
    const $link = find_dashboard_link(frm, 'Staff Profile');
    if (!$link.length) {
        return;
    }

    $link.closest('.document-link').find('.btn-new').css('visibility', 'hidden');
}


function update_staff_profile_dashboard(frm) {
    if (frm.doc.__islocal || !frm.doc.name) {
        return;
    }

    frappe.call({
        method: 'microsynth.qms.doctype.competency.competency.get_linked_staff_profiles',
        args: {
            docname: frm.doc.name
        },
        callback: function(response) {
            const data = response.message || {};
            const names = data.names || [];
            const $link = find_dashboard_link(frm, 'Staff Profile');

            set_dashboard_count($link, data.count || 0);
            set_dashboard_route_handler($link, 'Staff Profile', names);
        }
    });
}


function find_dashboard_link(frm, doctype) {
    let $link = frm.dashboard.transactions_area.find(`a[data-doctype="${doctype}"]`).first();
    if ($link.length) {
        return $link;
    }

    return frm.dashboard.transactions_area.find('a').filter(function() {
        return ($(this).text() || '').trim().startsWith(doctype);
    }).first();
}


function set_dashboard_count($link, count) {
    if (!$link || !$link.length) {
        return;
    }

    $link.find('.competency-linked-count').remove();
    $link.append(' <span class="competency-linked-count text-muted">&nbsp;&nbsp;' + count + '</span>');
}


function set_dashboard_route_handler($link, doctype, names) {
    if (!$link || !$link.length) {
        return;
    }

    $link.off('click.competency').on('click.competency', function(event) {
        event.preventDefault();
        if (names && names.length) {
            frappe.route_options = {
                name: ['in', names]
            };
            frappe.set_route('List', doctype, 'List');
            return;
        }

        frappe.route_options = {
            name: ['in', ['__no_linked_records__']]
        };
        frappe.set_route('List', doctype, 'List');
    });
}


function create_new_version(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.competency.competency.create_new_version',
        'args': {
            'docname': frm.doc.name
        },
        'callback': function(response) {
            if (response.message && response.message.name) {
                frappe.set_route('Form', 'Competency', response.message.name);
            }
        }
    });
}
