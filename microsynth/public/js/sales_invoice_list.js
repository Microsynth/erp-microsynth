// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['Sales Invoice'] = {
    onload: function(doc) {
        add_clear_button();
    },
    add_fields: ["customer", "customer_name", "base_grand_total", "outstanding_amount", "due_date", "company",
        "currency", "is_return"],
    get_indicator: function(doc) {
        var status_color = {
            "Draft": "grey",
            "Unpaid": "orange",
            "Paid": "green",
            "Return": "darkgrey",
            "Credit Note Issued": "darkgrey",
            "Unpaid and Discounted": "orange",
            "Overdue and Discounted": "red",
            "Overdue": "red"

        };
        return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
    },
    right_column: "grand_total"
};
