// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Process', {
    process_number: function(frm) {
        set_full_name(frm);
    },
    subprocess_number: function(frm) {
        set_full_name(frm);
    },
    all_chapters: function(frm) {
        set_full_name(frm);
    },
    chapter: function(frm) {
        set_full_name(frm);
    },
    process_name: function(frm) {
        set_full_name(frm);
    }
});

function set_full_name (frm) {
    if (frm.doc.process_number && frm.doc.subprocess_number && frm.doc.process_name) {
        if (frm.doc.all_chapters) {
            cur_frm.set_value("full_name", frm.doc.process_number + "." + frm.doc.subprocess_number + " " + frm.doc.process_name);
        }
        else {
            if (frm.doc.chapter) {
                cur_frm.set_value("full_name", frm.doc.process_number + "." + frm.doc.subprocess_number + "." + frm.doc.chapter + " " + frm.doc.process_name);
            }
        }
    }
}