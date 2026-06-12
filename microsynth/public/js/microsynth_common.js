/* common functions */

// naming series automation
function prepare_naming_series(frm) {
    locals.naming_series_map = null;
    // cache naming series
    frappe.call({
        'method': 'microsynth.microsynth.naming_series.get_naming_series',
        'args': {
            'doctype': (frm.doc.doctype === "Sales Invoice" && frm.doc.is_return === 1) ? "Credit Note" : frm.doc.doctype
        },
        'callback': function (r) {
            locals.naming_series_map = r.message;
        }
    });
    if (!frm.doc.__islocal) {
        // lock company on saved records (prevent change due to naming series)
        cur_frm.set_df_property('company', 'read_only', 1);
    }
}

function set_naming_series(frm) {
    if (locals.naming_series_map) {
        cur_frm.set_value("naming_series", locals.naming_series_map[frm.doc.company]);
    } else {
        setTimeout(() => { set_naming_series(frm); }, 1000);
    }
}

// mark navbar in specific colour
window.onload = async function () {
    await sleep(1000);
    var navbars = document.getElementsByClassName("navbar");
    if (navbars.length > 0) {
        if (window.location.hostname.includes("erp-test") || (window.location.hostname.includes("localhost"))) {
            navbars[0].style.backgroundColor = "#e65023";
        }
    }
}

// access protection of the file manager
$(document).ready(function() {
    // access protection: user shall not go to the file manager
    if (!frappe.user.has_role("System Manager")) {
        if ((window.location.href.includes("/desk#List/File/")) || (window.location.href.includes("/desk#Form/File/"))) {
            window.location.replace("/desk");
        }
    }
    // disable stop_drop handler by default - i.e. on each access, potentially lingering stop_drops are disabled
    // window.removeEventListener("drop", stop_drop, true); // disabled because this trigger only works once and not on each document refresh
});

function sleep(milliseconds) {
   return new Promise(resolve => setTimeout(resolve, milliseconds));
}

// hide chart buttons on reports
function hide_chart_buttons() {
    setTimeout(function() {
        frappe.query_report.page.remove_inner_button( __("Set Chart") );
        frappe.query_report.page.remove_inner_button( __("Hide Chart") );
    }, 500);
}

// hide column filters on reports
function hide_column_filters() {
    let container = document.getElementsByClassName("page-content");
    const hide_column_filter_style = document.createElement("style");
    hide_column_filter_style.innerHTML = `
        .dt-header .dt-row[data-is-filter] {
          display: none !important;
        }
    `
    for (let i = 0; i < container.length; i++) {
        container[i].appendChild(hide_column_filter_style);
    }
}

function hide_in_words() {
    // remove in words (because customisation and setting both do not apply)
    cur_frm.set_df_property('in_words', 'hidden', 1);
    cur_frm.set_df_property('base_in_words', 'hidden', 1);
    // this all does not work on base_in_words :-( last resort
    $("[data-fieldname='base_in_words']").hide();
}

// access protection: disable removing attachments
function access_protection() {
    // disable all attachments
    var styleSheet = document.createElement("style");
    styleSheet.innerText = ".attachment-row .close { display: none !important; }";
    document.head.appendChild(styleSheet);
}

// this function voids the above access protection
function remove_access_protection() {
    $('style').remove();
}

// QM Documents: remove action button for list and report to prevent illegal actions
if (window.location.href.includes("/desk#List/QM%20Document/")) {
    var css = ".btn-primary.dropdown-toggle { display: none; }";
    var head = document.head || document.getElementsByTagName('head')[0];
    var style = document.createElement('style');
    head.appendChild(style);
    style.type = 'text/css';
    style.appendChild(document.createTextNode(css));
}

function force_cancel(dt, dn) {
    frappe.confirm(
        __("Are you sure that you want to set this draft directly to the cancelled state?"),
        function () {
            // yes
            frappe.call({
                'method': 'microsynth.microsynth.utils.force_cancel',
                'args': {
                    'dt': dt,
                    'dn': dn
                },
                callback: function(r){
                    cur_frm.reload_doc();
                }
            });
        },
        function () {
            // no: do nothing
        }
    );
}

// Add the clear button. Call this function in the onload trigger of doctype_list.js
function add_clear_button() {
    var filter_bar = document.getElementsByClassName("page-form");
    var btn_clear = document.createElement("div");
    btn_clear.setAttribute('class', 'form-group frappe-control input-max-width col-md-2');
    btn_clear.innerHTML = "<button id='btn_clear' class='btn text-muted'>Clear</button>";
    for (var i = 0; i < filter_bar.length; i++) {
        filter_bar[i].appendChild(btn_clear);
        document.getElementById("btn_clear").onclick = clear_filters;
    }
}

// this is embedded in doctype_list.js functions to clear all filters
function clear_filters() {
    var standard_filters = {};
    var fields = frappe.meta.docfield_list[cur_list.meta.name];
    for (var i = 0; i < fields.length; i++) {
        if (fields[i].in_standard_filter === 1) {
            standard_filters[fields[i].fieldname] = '';
        }
    }
    frappe.set_route("List", cur_list.meta.name, standard_filters);
}

function fetch_accounting_notes(frm) {
    frappe.call({
        'method': 'microsynth.microsynth.doctype.accounting_note.accounting_note.get_accounting_notes_html',
        'args': {
            'reference_name': frm.doc.name
        },
        'callback': function (response) {
            frm.dashboard.add_comment(response.message, 'yellow', true);
        }
    });
}

// this is a handler function that prevents anything from being dropped on a form
function stop_drop(event) {
    event.stopImmediatePropagation();
}
