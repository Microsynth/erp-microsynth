// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Revenue Export"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        ,
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "fiscal_year",
            "label": __("Fiscal Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("fiscal_year") || frappe.defaults.get_global_default("fiscal_year")
        },
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": [ '', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December' ]
        }
    ],
    "onload": (report) => {
        report.page.add_inner_button(__('Download CSV'), function () {
           download_csv();
        });
    }
};

function download_csv() {
    //  call server to prepare csv content
    console.log("Let's go...");
    frappe.call({
        'method': "microsynth.microsynth.report.revenue_export.revenue_export.download_data",
        'args': {
            'filters': frappe.query_report.get_filter_values(),
            'save_to': "/tmp/revenue_export.csv"
        },
        'freeze': true,
        'freeze_message': __("Generating CSV, please have some patience..."),
        'callback': function(response) {
            console.log("I'm back");
            var csv = response.message;
            
            download("revenue_export.csv", csv);
            //console.log(csv);
        }
    });
}

function download(filename, content) {
    var element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(content));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}
