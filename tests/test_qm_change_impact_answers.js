const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(path.join(__dirname, '../microsynth/qms/doctype/qm_change/qm_change.js'), 'utf8');
const start = source.indexOf('        // Apply the strict edit rules');
const end = source.indexOf('        // BUTTONS', start);
assert.ok(start >= 0 && end > start);
const locking = source.slice(start, end);
const gridSource = fs.readFileSync(path.join(__dirname, '../../frappe/frappe/public/js/frappe/form/grid.js'), 'utf8');
const methodStart = gridSource.indexOf('\tupdate_docfield_property(fieldname, property, value) {');
const methodEnd = gridSource.indexOf('\n\t}', methodStart) + 3;
assert.ok(methodStart >= 0 && methodEnd > methodStart);
const Grid = vm.runInNewContext(`(class Grid { ${gridSource.slice(methodStart, methodEnd)} })`);

const fields = () => [
    { fieldname: 'qm_change_impact', read_only: false },
    { fieldname: 'impact_answer', read_only: false }
];

for (const status of ['Assessment & Classification', 'Planning', 'Implementation']) {
    const grid = new Grid();
    grid.docfields = fields();
    grid.fields_map = Object.fromEntries(grid.docfields.map(field => [field.fieldname, field]));
    grid.grid_rows = [{ docfields: fields() }];
    grid.debounced_refresh = () => {};
    const properties = { closure_comments: { read_only: false } };
    const doc = {
        status, regulatory_classification: 'GMP', created_by: 'creator@example.com',
        impact: [{ qm_change_impact: 'Quality', impact_answer: 'yes' }]
    };
    const frm = {
        doc,
        set_df_property(field, property, value) {
            properties[field] = { ...properties[field], [property]: value };
        },
        get_field: () => ({ grid }),
        refresh_field() {}
    };
    let isQau;
    const context = vm.createContext({
        frm, cur_frm: frm,
        frappe: {
            session: { user: 'creator@example.com' },
            user: { has_role: role => role === 'QAU' && isQau }
        }
    });
    for (isQau of [false, true, false]) {
        context.frappe.session.user = isQau ? 'qau@example.com' : 'creator@example.com';
        vm.runInContext(locking, context);
        assert.equal(properties.impact.read_only, !isQau, `${status}: table permission`);
        assert.equal(grid.fields_map.impact_answer.read_only, !isQau, `${status}: inline permission`);
        assert.equal(grid.grid_rows[0].docfields[1].read_only, !isQau, `${status}: row editor permission`);
        assert.equal(grid.docfields[1].read_only, !isQau, `${status}: new row permission`);
        assert.equal(grid.docfields[0].read_only, !(isQau && status === 'Assessment & Classification'));
        assert.equal(properties.closure_comments.read_only, false, `${status}: unrelated fields unchanged`);
        assert.equal(properties.customers.read_only, false, `${status}: references remain editable`);
        assert.equal(doc.impact[0].impact_answer, 'yes', `${status}: existing answers remain readable`);
    }
}

console.log('PASS: QAU and Creator Answer permissions for inline, row-editor and new-row fields in all three states');