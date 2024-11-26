// Copyright (c) 2023, libracore (https://www.libracore.com) and contributors
// For license information, please see license.txt


frappe.pages['approval-manager'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Approval Manager'),
        single_column: true
    });
    frappe.approval_manager.make(page);
    frappe.approval_manager.run();

    // add the application reference
    frappe.breadcrumbs.add("Microsynth");
}


frappe.approval_manager = {
    start: 0,
    make: function(page) {
        var me = frappe.approval_manager;
        me.page = page;
        me.body = $('<div></div>').appendTo(me.page.main);
        var data = "";
        $(frappe.render_template('approval_manager', data)).appendTo(me.body);
        // attach event handlers
        this.page.main.find("#reload").on('click', function() {
            // Reload page
            location.reload();
        });
    },
    run: function() { 
        // prepare user
        document.getElementById("user").value = frappe.session.user;
        frappe.approval_manager.get_approvals();
    },
    get_approvals: function() {
        frappe.call({
            'method': 'microsynth.microsynth.page.approval_manager.approval_manager.get_approvals',
            'args': {
                'user': frappe.session.user
            },
            'callback': function(r) {
                var approvals = r.message;
                frappe.approval_manager.display_approvals(approvals);
            }
        });
    },
    display_approvals: function(approvals) {
        // create rows
        var html = "";
        document.getElementById("approvals_view").innerHTML = "";
        for (var i = 0; i < approvals.length; i++) {
            html += approvals[i].html;
        }
        // insert content
        document.getElementById("approvals_view").innerHTML = html;

        // attach button handlers
        for (var i = 0; i < approvals.length; i++) {
            var btn_reject = document.getElementById("btn_reject_" + approvals[i].name);
            btn_reject.onclick = frappe.approval_manager.reject.bind(this, approvals[i].name);
            var btn_reassign = document.getElementById("btn_reassign_" + approvals[i].name);
            btn_reassign.onclick = frappe.approval_manager.reassign.bind(this, approvals[i].name);
            var btn_approve = document.getElementById("btn_approve_" + approvals[i].name);
            btn_approve.onclick = frappe.approval_manager.approve.bind(this, approvals[i].name);
            frappe.approval_manager.remove_clearfix_nodes();
        }
    },
    approve: function(pinv) {
        frappe.call({
            'method': 'microsynth.microsynth.page.approval_manager.approval_manager.approve',
            'freeze': true,
            'freeze_message': __("Approving..."),
            'args': {
                'pinv': pinv,
                'user': frappe.session.user
            },
            'callback': function(r) {
                document.getElementById("row_" + pinv).style.display = "none";
            }
        });
    },
    reassign: function(pinv) {
        // Show dialog for reason, allow to assign to a different person
        frappe.prompt([
            {'fieldname': 'new_assignee', 'fieldtype': 'Link', 'options': 'User', 'label': __('Assign to'), 'reqd': 1},
            {'fieldname': 'reason', 'fieldtype': 'Text', 'label': __('Reason')}
        ],
            function(values){
                frappe.call({
                    'method': 'microsynth.microsynth.page.approval_manager.approval_manager.reassign',
                    'freeze': true,
                    'freeze_message': __("Reassigning ..."),
                    'args': {
                        'pinv': pinv,
                        'user': frappe.session.user,
                        'reason': values.reason || "",
                        'new_assignee': values.new_assignee
                    },
                    'callback': function(r) {
                        document.getElementById("row_" + pinv).style.display = "none";
                    }
                });
            },
        __('Please reassign'),
        __('Reassign')
        );
    },
    reject: function(pinv) {
        // Show dialog for reason, allow to assign to a different person
        frappe.prompt([
            {'fieldname': 'reason', 'fieldtype': 'Text', 'label': __('Reason'), 'reqd': 1}
        ],
            function(values){
                frappe.call({
                    'method': 'microsynth.microsynth.page.approval_manager.approval_manager.reject',
                    'freeze': true,
                    'freeze_message': __("Rejecting ..."),
                    'args': {
                        'pinv': pinv,
                        'user': frappe.session.user,
                        'reason': values.reason
                    },
                    'callback': function(r) {
                        document.getElementById("row_" + pinv).style.display = "none";
                    }
                });
            },
        __('Please justify'),
        __('Reject')
        );
    },
    remove_clearfix_nodes: function() {
        let clearfixes = document.getElementsByClassName("clearfix"); 
        for  (let i = clearfixes.length - 1; i >= 0 ; i--) {
            clearfixes[i].remove();
        }
    }
}
