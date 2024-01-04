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
        this.page.main.find(".contact_1").on('change', function() {
            frappe.contact_merger.display_contact_details();
        });
        this.page.main.find(".contact_2").on('change', function() {
            frappe.contact_merger.display_contact_details();
        });
    },
    run: function() {
        
    },
    display_contact_details: function() {
        console.log("display...");
        frappe.call({
            'method': 'microsynth.microsynth.page.contact_merger.contact_merger.get_contact_details',
            'args': {
                'contact_1': document.getElementById("contact_1").value,
                'contact_2': document.getElementById("contact_2").value
            },
            'callback': function(r) {
                if (r.message) {
                    console.log(r.message);
                    try {
                        document.getElementById("table_placeholder").innerHTML = r.message.html;
                    } catch {
                        frappe.msgprint( "An error occurred while loading the contacts." );
                    }
                } 
            }
        })
    }
}

