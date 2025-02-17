frappe.pages['tracking_codes'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Tracking Codes',
        single_column: true
    });
    frappe.tracking_codes.make(page);
    frappe.tracking_codes.run();
}

frappe.tracking_codes = {
    start: 0,
    make: function(page) {
        var me = frappe.tracking_codes;
        me.page = page;
        me.body = $('<div></div>').appendTo(me.page.main);
        var data = "";
        $(frappe.render_template('tracking_codes', data)).appendTo(me.body);
    },
    run: function() {
        // add on enter listener to the input box
        document.getElementById("input").addEventListener("keyup", function(event) {
            event.preventDefault();
            if (event.keyCode === 13) {
                var input = this.value;

                // decide if input is web order id or tracking code
                if (7 <= input.length && input.length <= 8) {
                    // input is a web order id
                    document.getElementById("web_order_id").value = input;
                } else if (input.length >= 10) {
                    // input is a tracking code
                    document.getElementById("tracking_code").value = input;
                } else {
                    frappe.show_alert("Input is neither a web order ID nor a tracking code");
                }
                clear_input();

                var web_order_id = document.getElementById("web_order_id").value;
                var tracking_code = document.getElementById("tracking_code").value;

                if (web_order_id && tracking_code) {
                    // check tracking code
                    frappe.call({
                        'method': 'microsynth.microsynth.doctype.tracking_code.tracking_code.check_tracking_code',
                        'args': {
                            'web_order_id': web_order_id,
                            'tracking_code': tracking_code
                        },
                        'async': true,
                        'freeze': true,
                        'freeze_message': __("Checking Tracking Code ..."),
                        'callback': function(r) {
                            if (r.message.success) {
                                create_tracking_code(web_order_id, tracking_code);
                                setTimeout(function() { 
                                    clear_fields();
                                    web_order_id = null;
                                    tracking_code = null;
                                }, 300 );
                            } else {
                                frappe.confirm(
                                    __("Are you sure that the tracking code '" + tracking_code + "' and the Web Order ID '" + web_order_id + "' are correct?<br>" + r.message.message),
                                    function () {
                                        // yes
                                        create_tracking_code(web_order_id, tracking_code);
                                        setTimeout(function() { 
                                            clear_fields();
                                            web_order_id = null;
                                            tracking_code = null;
                                        }, 300 );
                                        frappe.show_alert( __("Created Tracking Code anyway.") );
                                    },
                                    function () {
                                        // no
                                        setTimeout(function() { 
                                            clear_fields();
                                            web_order_id = null;
                                            tracking_code = null;
                                        }, 300 );
                                        frappe.show_alert( __("Please enter Web Order ID and tracking code again.") );
                                    }
                                );
                            }
                        }
                    })
                } else {
                    // frappe.show_alert("one field missing");
                }
            }
        });
    }
}

function create_tracking_code(web_order_id, tracking_code) {
    frappe.call({
        'method': 'microsynth.microsynth.doctype.tracking_code.tracking_code.create_tracking_code',
        'args': {
            'web_order_id': web_order_id,
            'tracking_code': tracking_code
        }, 
        'callback': function(r) {
            console.log(r.message);
        }
    })
}

function clear_input() {
    document.getElementById("input").value = "";
}

function clear_fields() {
    clear_input();
    document.getElementById("web_order_id").value = "";
    document.getElementById("tracking_code").value = "";
}