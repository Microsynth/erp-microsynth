// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


var global_onload = frappe.listview_settings['Sales Order'].onload;
frappe.listview_settings['Sales Order'].onload = function (doclist) {
    if (global_onload) {
        global_onload(doclist);
    }
    add_clear_button();
}
