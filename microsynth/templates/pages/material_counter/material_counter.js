$('document').ready(function(){
    make();
    run();
});

function make() {
}

function run() {
    frappe.call({
        'method': 'microsynth.templates.pages.material_counter.material_counter.get_processes',
        'callback': function(r) {
            console.log(r);
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
    console.log(process.value);
    // TODO: backend function that retuns the Users by process.name
}