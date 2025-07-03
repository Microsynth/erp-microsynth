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

    // Scan data matrix code
    $('#scanner_input').on('keypress', function (e) {
        if (e.which === 13) {
            let value = $(this).val().trim();
            $(this).val(""); // Clear input

            let item_code, batch_no = "";
            let qty_editable = "";

            if (value.includes(":")) {
                [item_code, batch_no] = value.split(":");
                qty_editable = "readonly"; // If batch number is present, set qty to readonly
            } else {
                item_code = value;
            }
            frappe.call({
                'method': 'microsynth.templates.pages.material_counter.material_counter.get_item_details',
                'args': { 'item_code': item_code },
                callback: function (r) {
                    if (r.message) {
                        let item = r.message;
                        let row = `
                            <tr>
                                <td><button class="btn btn-danger btn-sm remove-row">×</button></td>
                                <td>${item.name}</td>
                                <td>${item.item_name}</td>
                                <td>${item.material_code || ""}</td>
                                <td><input type="number" value="1" min="1" class="form-control qty-input" onchange="focus_on_scanner_input()" ${qty_editable}></td>
                                <td>${batch_no}</td>
                            </tr>`;
                        $('#item_table tbody').append(row);
                    } else {
                        frappe.msgprint(`Item ${item_code} not found.`);
                    }
                }
            });
        }
    });

    // Handle remove row
    $('#item_table').on('click', '.remove-row', function () {
        $(this).closest('tr').remove();
        focus_on_scanner_input();
    });

    // Check Out button
    $('#checkout_button').on('click', function () {
        let warehouse = $('#warehouse').val();
        let user = $('#users').val();
        if (!warehouse) {
            frappe.msgprint("Warehouse is required.");
            return;
        }
        if (!user) {
            frappe.msgprint("User is required.");
            return;
        }

        let items = [];
        $('#item_table tbody tr').each(function () {
            let cells = $(this).find('td');
            let batch_no = $(cells[5]).text().trim();
            let item = {
                'item_code': $(cells[1]).text().trim(),
                'qty': parseFloat($(cells[4]).find('input').val()) || 1
            };
            if (batch_no) {
                item['batch_no'] = batch_no;
            }
            items.push(item);
        });

        if (!items.length) {
            frappe.msgprint("No items to check out.");
            return;
        }

        frappe.call({
            'method': 'microsynth.templates.pages.material_counter.material_counter.create_stock_entry',
            'args': {
                'items': items,
                'warehouse': warehouse,
                'user': user
            },
            callback: function (r) {
                if (r.message) {
                    frappe.msgprint({
                        'title': "Success",
                        'message': "Stock Entry <b>" + r.message + "</b> was created.",
                        'indicator': "green"
                    });
                    $('#item_table tbody').empty(); // Clear the table
                } else {
                    frappe.msgprint("Failed to create Stock Entry.");
                }
            }
        });
    });
    focus_on_scanner_input();
}

function focus_on_scanner_input() {
    $('#scanner_input').focus();
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
