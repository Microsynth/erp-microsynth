/* common functions */


// naming series automation
function prepare_naming_series(frm) {
    locals.naming_series_map = null;
    // cache naming series
    frappe.call({
        'method': 'microsynth.microsynth.naming_series.get_naming_series',
        'args': {
            'doctype': frm.doc.doctype
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
        if (window.location.hostname.includes("erp-test")) {
            navbars[0].style.backgroundColor = "#e65023";
        }
    }
}

function sleep(milliseconds) {
   return new Promise(resolve => setTimeout(resolve, milliseconds));
}
