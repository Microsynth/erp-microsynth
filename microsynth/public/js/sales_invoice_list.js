// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


var global_onload = frappe.listview_settings['Sales Invoice'].onload;
frappe.listview_settings['Sales Invoice'].onload = function (doclist) {
    // Precaution in case onload event is added to sales_invoice.js in the future
    if (global_onload) {
        global_onload(doclist);
    }
    add_clear_button();
}
