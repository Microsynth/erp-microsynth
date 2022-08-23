// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Label Orders"] = {
    "filters": [

    ],
    "onload": (report) => {
        report.page.add_inner_button( __("Pick labels"), function() {
            pick_wizard();
        }
    }
};

function pick_wizard() {
    // show scan dialog
    
    // create delivery note / pdf
    
    // open print dialog & print
    
}
