frappe.pages['contact_merger'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Contact Merger',
        single_column: true
    });

    frappe.contact_merger.make(page);
    frappe.contact_merger.run();

    // add the application reference
    frappe.breadcrumbs.add("Microsynth");
}


frappe.contact_merger = {
    start: 0,
    make: function(page) {
        var me = frappe.contact_merger;
        me.page = page;
        me.body = $('<div></div>').appendTo(me.page.main);
        var data = "";
        $(frappe.render_template('contact_merger', data)).appendTo(me.body);

        // attach event handlers
        this.page.main.find("#contact_1").on('change', function() {
            frappe.contact_merger.display_contact_details();
        });
        this.page.main.find("#contact_2").on('change', function() {
            frappe.contact_merger.display_contact_details();
        });
        this.page.main.find("#merge").on('click', function() {
            frappe.contact_merger.merge_contact();
        });
        this.page.main.find("#reload").on('click', function() {
            frappe.contact_merger.reload_contacts();
        });
        this.page.main.find("#switch").on('click', function() {
            frappe.contact_merger.switch_contacts();
        });
        this.page.main.find("#btn_contact_1").on('click', function() {
            frappe.contact_merger.open_contact_1();
        });
        this.page.main.find("#btn_contact_2").on('click', function() {
            frappe.contact_merger.open_contact_2();
        });
    },
    run: function() {
        // read command line arguments
        frappe.contact_merger.get_request_arguments();
    },
    display_contact_details: function() {
        frappe.call({
            'method': 'microsynth.microsynth.page.contact_merger.contact_merger.get_contact_details',
            'args': {
                'contact_1': document.getElementById("contact_1").value,
                'contact_2': document.getElementById("contact_2").value
            },
            'callback': function(r) {
                if (r.message) {
                    try {
                        document.getElementById("table_placeholder").innerHTML = r.message.html;

                        // Save contact_2.has_webshop_account to a hidden data attribute
                        document.getElementById("contact_2").dataset.hasWebshopAccount = r.message?.data?.contact_2?.has_webshop_account || "0";
                        // Optional chaining (modern JavaScript)
                        // ?. means "only access if the preceding is not null/undefined"

                        frappe.contact_merger.attach_toggle_handlers();
                    } catch {
                        frappe.msgprint( "An error occurred while loading the contacts." );
                    }
                }
            }
        });
    },
    attach_toggle_handlers: function() {
        // add toggle handler to each button with class btn-toggle
        this.page.main.find(".btn-toggle").on('click', function(btn) {
            frappe.contact_merger.toggle(btn.target.id);
        });
        // check and enable merge button
        if ((document.getElementById("contact_1").value)
            && (document.getElementById("contact_2").value)
            && (document.getElementById("contact_1").value !== document.getElementById("contact_2").value)) {
                document.getElementById("merge").disabled = false;
        } else {
            document.getElementById("merge").disabled = true;
        }
    },
    toggle: function(button) {
        document.getElementById(button).classList.add("btn-primary");
        if (button.endsWith("_1")) {
            document.getElementById(button.replace("_1", "_2")).classList.remove("btn-primary");
        } else {
            document.getElementById(button.replace("_2", "_1")).classList.remove("btn-primary");
        }
    },
    merge: function(values) {
        frappe.call({
            'method': 'microsynth.microsynth.page.contact_merger.contact_merger.merge_contacts',
            'args': {
                'contact_1': document.getElementById("contact_1").value,
                'contact_2': document.getElementById("contact_2").value,
                'values': values
            },
            'freeze': true,
            'freeze_message': __("&#129668; Merging Contact '" + document.getElementById("contact_2").value + "' into Contact '" + document.getElementById("contact_1").value + "' ..."),
            'callback': function(r) {
                if (r.message) {
                    if (r.message.error) {
                        frappe.msgprint( r.message.error , "Error" );
                    } else {
                        document.getElementById("contact_1").value = r.message.contact;
                        document.getElementById("contact_2").value = "";
                        frappe.contact_merger.display_contact_details();
                    }
                }
            }
        });
    },
    merge_contact: function() {
        var values = {};
        var buttons = document.getElementsByClassName("btn-toggle btn-primary");
        for (var i = 0; i < buttons.length; i++) {
            values[buttons[i].dataset.fieldname] = buttons[i].dataset.value;
        }
        // Show a warning if Contact 2 has a Webshop Account
        if (document.getElementById("contact_2").dataset.hasWebshopAccount == "1") {
            frappe.confirm(
                'Are you sure you want to <b>delete the Contact ' +
                document.getElementById("contact_2").value +
                ' with a Webshop Account</b> by merging it into ' +
                document.getElementById("contact_1").value +
                '?<br>Contact ' + document.getElementById("contact_2").value +
                ' <b>will lose</b> its <b>access to the Webshop</b>.',
                () => {
                frappe.contact_merger.merge(values);
            }, () => {
                frappe.show_alert('No merge done');
            });
        } else {
            frappe.contact_merger.merge(values);
        }
    },
    reload_contacts: function() {
        document.getElementById("contact_1").value = document.getElementById("contact_1").value;
        document.getElementById("contact_2").value = document.getElementById("contact_2").value;
        frappe.contact_merger.display_contact_details();
    },
    switch_contacts: function() {
        var tmp = document.getElementById("contact_1").value;
        document.getElementById("contact_1").value = document.getElementById("contact_2").value;
        document.getElementById("contact_2").value = tmp;
        frappe.contact_merger.display_contact_details();
    },
    open_contact_1: function() {
        var contact_1 = document.getElementById("contact_1").value;
        var target = "/desk" + frappe.utils.get_form_link("Contact", contact_1);
        window.open(target);
    },
    open_contact_2: function() {
        var contact_2 = document.getElementById("contact_2").value;
        var target = "/desk" + frappe.utils.get_form_link("Contact", contact_2);
        window.open(target);
    },
    get_request_arguments: function() {
        // get command line parameters
        var arguments = window.location.toString().split("?");
        if (!arguments[arguments.length - 1].startsWith("http")) {
            var args_raw = arguments[arguments.length - 1].split("&");
            var args = {};
            args_raw.forEach(function (arg) {
                var kv = arg.split("=");
                if (kv.length > 1) {
                    args[kv[0]] = kv[1];
                }
            });
            var has_contacts = false;
            if (args['contact_1']) {
                document.getElementById('contact_1').value = args['contact_1'];
                has_contacts = true;
            }
            if (args['contact_2']) {
                document.getElementById('contact_2').value = args['contact_2'];
                has_contacts = true;
            }
            if (has_contacts) {
                frappe.contact_merger.display_contact_details();
            }
        }
    }
}
