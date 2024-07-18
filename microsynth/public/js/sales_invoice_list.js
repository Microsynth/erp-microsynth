// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

// render
frappe.listview_settings['Sales Invoice'] = {
    onload: function(doc) {
        var filter_bar = document.getElementsByClassName("page-form");
        var btn_clear = document.createElement("div");
        btn_clear.setAttribute('class', 'form-group frappe-control input-max-width col-md-2');
        btn_clear.innerHTML = "<button id='btn_clear' class='btn text-muted'>Clear</button>";
        for (var i = 0; i < filter_bar.length; i++) {
            filter_bar[i].appendChild(btn_clear);
            document.getElementById("btn_clear").onclick = clear_filters;
        }
    }
};
