$('document').ready(function(){
    make();
    run();
});

function make() {
}

function run() {
    // get command line parameters
    var arguments = window.location.toString().split("?");
    if (!arguments[arguments.length - 1].startsWith("http")) {
        var args_raw = arguments[arguments.length - 1].split("&");
        var args = {};
        args_raw.forEach(function (arg) {
            var kv = arg.split("=");
            if (kv.length > 1) {
                args[kv[0]] = kv[1];
            }
        });
        if (args['warehouse']) {
            let warehouse = decodeURI(args['warehouse']);
            console.log(warehouse);
            document.getElementById('warehouse').value = warehouse;
        }
    }
    
    frappe.call({
        'method': 'microsynth.templates.pages.material_counter.material_counter.get_processes',
        'callback': function(r) {
            let select = document.getElementById('processes');
            if (r.message) {
                for (i = 0; i < r.message.length; i++) {
                    select.innerHTML += "<option value=\"" + r.message[i] 
                        + "\">" + r.message[i] + "</option>";
                }
            }
        }
    });
}

function get_users_for_process(process) {
    frappe.call({
        'method': 'microsynth.templates.pages.material_counter.material_counter.get_user_names_by_process',
        'args': {"qm_process": process.value},
        'callback': function(r) {
            let select = document.getElementById('users');
            select.innerHTML = "";
            if (r.message) {
                for (i = 0; i < r.message.length; i++) {
                    select.innerHTML += "<option value=\"" + r.message[i] 
                        + "\">" + r.message[i] + "</option>";
                }
            }
        }
    });
}