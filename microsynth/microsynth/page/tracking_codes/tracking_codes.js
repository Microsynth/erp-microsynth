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
        document.getElementById("input").addEventListener("keyup", function(event) {
            event.preventDefault();
            if (event.keyCode === 13) {
                frappe.show_alert(this.value)

                // decide if input is web order id or tracking code
                // fill respective field
                // clear input field
                // if both web order id and tracking code are completed
                // write to db
                
                // timeout 1 s
                setTimeout(function() { 
                    clear_input();
                }, 1000 );
                // clear web order id and trakcing code


                if (this.value.startsWith("MA-")) {
                    // this is an employee key
                    var employee = document.getElementById("input");
                    employee.value = this.value;
                    this.value = "";
                    // reload work order if one is open
                    var work_order = document.getElementById("work_order_reference").value;
                    if (work_order) {
                        frappe.production_control.launch(work_order);
                    }
                } else {
                    // frappe.production_control.launch(this.value);
                    frappe.show_alert("clear")
                    // this.value = "";
                }
            }
        });
        // check for url parameters
        var url = location.href;
        if (url.indexOf("?work_order=") >= 0) {
            var work_order = url.split('=')[1].split('&')[0];
            document.getElementById("input").value = work_order;
            frappe.production_control.get_work_order(work_order);
        }
    }
    
}

function clear_input() {
    document.getElementById("input").value = "";
}