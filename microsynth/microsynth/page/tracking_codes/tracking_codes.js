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
        // add on enter listener to QR code box
        document.getElementById("web_order_id").addEventListener("keyup", function(event) {
            event.preventDefault();
            if (event.keyCode === 13) {
                if (this.value.startsWith("MA-")) {
                    // this is an employee key
                    var employee = document.getElementById("tracking_code");
                    employee.value = this.value;
                    this.value = "";
                    // reload work order if one is open
                    var work_order = document.getElementById("work_order_reference").value;
                    if (work_order) {
                        frappe.production_control.launch(work_order);
                    }
                } else {
                    frappe.production_control.launch(this.value);
                    this.value = "";
                }
            }
        });
        // check for url parameters
        var url = location.href;
        if (url.indexOf("?work_order=") >= 0) {
            var work_order = url.split('=')[1].split('&')[0];
            document.getElementById("web_order_id").value = work_order;
            frappe.production_control.get_work_order(work_order);
        }
    }
    
}

function clear_qr() {
    document.getElementById("web_order_id").value = "";
}