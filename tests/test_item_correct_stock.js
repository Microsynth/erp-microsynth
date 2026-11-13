const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const requests = [];
const messages = [];
let dialog;
const context = {
    __: (value, args = []) => value.replace(/\{(\d+)\}/g, (match, index) => args[index]),
    cint: value => parseInt(value, 10),
    flt: value => Number(value),
    frappe: {
        utils: { escape_html: value => String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;") },
        defaults: { get_default: () => 2 },
        call: options => requests.push(options),
        msgprint: message => messages.push(message),
        ui: {
            form: { on() {} },
            Dialog: class {
                constructor(options) {
                    dialog = this;
                    this.options = options;
                    this.warehouse = "Stores - BAL";
                    const df = options.fields.find(field => field.fieldname === "batch_table");
                    const grid = {
                        controls: [],
                        refresh() {
                            this.controls = df.data.map((row, index) =>
                                this.controls[index] || { doc: row }
                            );
                        }
                    };
                    this.fields_dict = { batch_table: { df, grid } };
                    this.$wrapper = { find: () => ({ css() {} }) };
                }
                get_value() { return this.warehouse; }
                get_values() {
                    return {
                        warehouse: this.warehouse,
                        batch_table: this.fields_dict.batch_table.df.data
                    };
                }
                show() {}
                hide() {}
                disable_primary_action() {}
                enable_primary_action() {}
            }
        }
    }
};

vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, "../microsynth/public/js/item.js"), "utf8"), context);
let reloads = 0;
context.open_correct_stock_dialog({
    doc: { name: "TEST", stock_uom: "Unit" },
    reload_doc() { reloads++; }
});
const warehouseField = dialog.options.fields.find(field => field.fieldname === "warehouse");
const table = dialog.fields_dict.batch_table;
warehouseField.onchange();
assert.equal(requests.length, 1, "initial warehouse must not be loaded twice");
requests[0].callback({ message: [{ batch_no: "A", current_qty: 10 }] });

table.grid.controls[0].doc.new_qty = 7;
table.grid.refresh();
assert.equal(table.df.data[0].new_qty, 7, "quantity must survive blur and refresh");
warehouseField.onchange();
assert.equal(requests.length, 1, "same warehouse must not reload over edits");

dialog.warehouse = "Other";
warehouseField.onchange();
requests[1].callback({ message: [{ batch_no: "B", current_qty: 20 }] });
assert.strictEqual(table.grid.controls[0].doc, table.df.data[0], "reused controls must retain the active row reference");
assert.equal(table.df.data[0].current_qty, 20);
assert.equal(table.df.data[0].new_qty, 20);
table.grid.controls[0].doc.new_qty = 0;
table.grid.refresh();
assert.equal(table.df.data[0].new_qty, 0, "zero quantity must persist");
dialog.options.primary_action();
assert.equal(messages.length, 0);
assert.equal(requests[2].args.rows[0].new_qty, 0, "submitted quantity must match the edit");
assert.equal(requests[2].args.rows[0].batch_no, "B");
assert.equal(requests[2].args.warehouse, "Other");

dialog.warehouse = "Slow";
warehouseField.onchange();
const staleRequest = requests[3];
dialog.warehouse = "Latest";
warehouseField.onchange();
requests[4].callback({ message: [{ batch_no: "C", current_qty: 30 }] });
staleRequest.callback({ message: [{ batch_no: "STALE", current_qty: 99 }] });
assert.equal(table.df.data[0].batch_no, "C", "stale responses must be ignored");

dialog.warehouse = "Retry";
warehouseField.onchange();
requests[5].error();
warehouseField.onchange();
assert.equal(requests.length, 7, "failed loads must be retryable");
requests[6].callback({ message: [] });
assert.equal(table.df.data.length, 0, "empty warehouse must clear old rows");
assert.equal(table.grid.controls.length, 0);

dialog.warehouse = "Closing";
warehouseField.onchange();
dialog.onhide();
requests[7].callback({ message: [{ batch_no: "CLOSED", current_qty: 1 }] });
assert.equal(table.df.data.length, 0, "closed dialogs must ignore pending responses");

requests[2].callback({ message: {
    success: true, changed_batches: 1, issue_stock_entry: "ENTRY/TEST", receipt_stock_entry: null
} });
assert.equal(dialog.options.title, "Success");
assert.ok(dialog.options.fields[0].options.includes("1 batch(es) corrected."));
assert.ok(dialog.options.fields[0].options.includes("/app/stock-entry/ENTRY%2FTEST"));
assert.equal(reloads, 1);
assert.equal(messages.length, 0, "success must not reuse the shared message dialog");

console.log("PASS: stock dialog edit persistence, zero submission, warehouse reloads, stale responses, retry, empty results and close");