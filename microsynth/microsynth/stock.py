
import json
import frappe
from microsynth.microsynth.utils import user_has_role
from microsynth.microsynth.labels import print_purchasing_labels

def get_purchasing_items(company="Microsynth AG"):
    """
    Returns purchasing items including default_warehouse for the given company.

    bench execute microsynth.microsynth.stock.get_purchasing_items --kwargs '{"company": "Microsynth AG"}'
    """
    query = """
        SELECT
            `tabItem`.`item_code`,
            `tabItem`.`item_name`,
            `tabItem`.`material_code`,
            `tabItem Default`.`default_warehouse`,
            `tabItem`.`stock_uom`,
            `tabItem`.`pack_size`,
            `tabItem`.`pack_uom`
        FROM
            `tabItem`
        LEFT JOIN
            `tabItem Default`
                ON `tabItem Default`.`parent` = `tabItem`.`name`
                AND `tabItem Default`.`company` = %(company)s
        WHERE
            `tabItem`.`is_purchase_item` = 1
            AND `tabItem`.`disabled` = 0
            AND `tabItem`.`item_group` = 'Purchasing'
        ORDER BY
            `tabItem`.`item_name` ASC
    """
    return frappe.db.sql(query, {"company": company}, as_dict=True)


@frappe.whitelist(methods=["POST"])
def issue_material(company, user, items):
    """
    API endpoint to create a Material Issue Stock Entry with validation.

    Expected JSON:
    {
        "company": "Microsynth AG",
        "user": "firstname.lastname@microsynth.ch",
        "items": [
            {
                "item_code": "P012345",
                "qty": 3,
                "warehouse": "Stores - BAL",
                "batch_no": "ABC123456789"
            }
        ]
    }

    bench execute microsynth.microsynth.stock.issue_material --kwargs '{"company": "Microsynth AG", "user": "firstname.lastname@microsynth.ch", "items": [{"item_code": "P007441", "qty": 2, "warehouse": "Stores - BAL", "batch_no": "HMBJ7023-HMBK0735"}]}'
    """
    try:
        if isinstance(items, str):
            items = json.loads(items)

        if not company:
            frappe.throw("Field 'company' is required.")
        if not items or not isinstance(items, list):
            frappe.throw("Field 'items' must be a non-empty list.")

        # Create Stock Entry
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.company = company
        stock_entry.owner = user

        # Build child rows
        for entry in items:
            item_code = entry.get("item_code")
            qty = entry.get("qty")
            warehouse = entry.get("warehouse")
            batch_no = entry.get("batch_no")

            if not item_code:
                frappe.throw("Each item requires 'item_code'.")
            if qty is None:
                frappe.throw(f"Item {item_code}: field 'qty' is required.")
            if qty <= 0:
                frappe.throw(f"Item {item_code}: quantity must be greater than zero.")
            if not warehouse:
                frappe.throw(f"Item {item_code}: field 'warehouse' is required.")

            # Check batch requirement
            has_batch = frappe.db.get_value("Item", item_code, "has_batch_no")
            if has_batch and not batch_no:
                frappe.throw(f"Item '{item_code}' requires a batch number, but 'batch_no' was not provided.")

            # Append child row
            row = {
                "item_code": item_code,
                "qty": qty,
                "s_warehouse": warehouse
            }
            if batch_no:
                row["batch_no"] = batch_no

            stock_entry.append("items", row)

        # Save + submit
        stock_entry.insert()
        stock_entry.submit()
        frappe.db.commit()

        return {
            "message": {
                "success": True,
                "message": "OK",
                "internal_message": ""
            }
        }

    except Exception as e:
        frappe.local.response.http_status_code = 500
        return {
            "message": {
                "success": False,
                "message": "Error",
                "internal_message": str(e) + "\n" + str(frappe.get_traceback())
            }
        }


def create_stock_entry(item, warehouse, rows, purpose):
    doc = frappe.new_doc("Stock Entry")
    doc.stock_entry_type = purpose
    doc.company = frappe.defaults.get_user_default("Company")

    for r in rows:
        doc.append("items", {
            "item_code": item.name,
            "qty": r["qty"],
            "uom": item.stock_uom,
            "conversion_factor": 1,
            "basic_rate": r.get("rate", 0),
            "valuation_rate": r.get("rate", 0),
            "allow_zero_valuation": 1 if r.get("rate", 0) == 0 else 0,
            "s_warehouse": warehouse if purpose == "Material Issue" else None,
            "t_warehouse": warehouse if purpose == "Material Receipt" else None,
            "batch_no": r["batch_no"]
        })

    doc.insert()
    doc.submit()
    return doc


def create_generic_batch(item_code, batch_no):
    doc = frappe.new_doc("Batch")
    doc.item = item_code
    doc.batch_id = batch_no
    doc.insert(ignore_permissions=True)


def get_batch_rate(item_code, batch_no):
    if batch_no.startswith("[NA]"):
        return 0

    rate = frappe.db.sql("""
        SELECT `valuation_rate`
        FROM `tabPurchase Receipt Item`
        WHERE
            `item_code` = %s
            AND `batch_no` = %s
            AND `docstatus` = 1
        ORDER BY `creation` DESC
        LIMIT 1
    """, (item_code, batch_no))

    return rate[0][0] if rate else 0


def get_shelf_life_date(item, batch_no):
    expiry = frappe.db.get_value("Batch", batch_no, "expiry_date")
    if expiry:
        return expiry

    if item.shelf_life_in_days:
        return frappe.utils.add_days(frappe.utils.nowdate(), item.shelf_life_in_days)

    return None


def get_internal_code(name):
    if len(name) >= 5 and name[-5] == "0":
        return name[-4:]
    return ""


@frappe.whitelist()
def get_batches_with_qty(item_code, warehouse):
    """
    Get batches for a given item and warehouse along with their current quantities.
    Creates a generic batch if none exist to allow stock correction.

    bench execute microsynth.microsynth.stock.get_batches_with_qty --kwargs '{"item_code": "P002005", "warehouse": "Stores - BAL"}'
    """
    batches = frappe.db.sql("""
        SELECT
            `tabBatch`.`name` AS `batch_no`
        FROM `tabBatch`
        WHERE `tabBatch`.`item` = %s
        ORDER BY `tabBatch`.`creation`
    """, item_code, as_dict=True)

    # Ensure generic batch exists
    generic_batch = f"[NA]-{item_code}"
    batch_list = [b.batch_no for b in batches]
    if generic_batch not in batch_list:
        batch_list.append(generic_batch)

    result = []

    for batch_no in batch_list:
        qty = frappe.db.sql("""
            SELECT IFNULL(SUM(`actual_qty`), 0)
            FROM `tabStock Ledger Entry`
            WHERE
                `item_code` = %s
                AND `warehouse` = %s
                AND `batch_no` = %s
                AND `is_cancelled` = 0
        """, (item_code, warehouse, batch_no))[0][0]

        result.append({
            "batch_no": batch_no,
            "current_qty": qty,
            "new_qty": qty
        })

    return result


@frappe.whitelist()
def correct_stock(item_code, warehouse, rows):
    """
    Correct stock levels for a given item and warehouse based on provided batch quantities.
    """
    # Check that User has Role "Stock User"
    if not user_has_role(frappe.session.user, "Stock User"):
        frappe.throw("You do not have permission to perform this action.")

    rows = frappe.parse_json(rows)
    item = frappe.get_doc("Item", item_code)
    issue_rows = []
    receipt_rows = []
    label_table = []
    any_change = False
    generic_batch = f"[NA]-{item_code}"

    for row in rows:
        batch_no = row["batch_no"]

        current_qty = frappe.db.sql("""
            SELECT IFNULL(SUM(`actual_qty`), 0)
            FROM `tabStock Ledger Entry`
            WHERE
                `item_code` = %s
                AND `warehouse` = %s
                AND `batch_no` = %s
                AND `is_cancelled` = 0
        """, (item_code, warehouse, batch_no))[0][0]

        new_qty = float(row["new_qty"])
        delta = new_qty - current_qty

        if abs(delta) < 0.0001:
            continue

        if batch_no == generic_batch and not frappe.db.exists("Batch", generic_batch):
            create_generic_batch(item_code, generic_batch)

        any_change = True

        if delta < 0:
            if current_qty + delta < 0:
                frappe.throw(f"Negative stock not allowed for batch {batch_no}")

            issue_rows.append({
                "batch_no": batch_no,
                "qty": abs(delta)
            })

        else:
            rate = get_batch_rate(item_code, batch_no)

            receipt_rows.append({
                "batch_no": batch_no,
                "qty": delta,
                "rate": rate or 0.01
            })
            # Prepare label row
            shelf_life_date = get_shelf_life_date(item, batch_no)

            label_table.append({
                "labels_to_print": int(delta),
                "item_code": item.name,
                "item_name": item.item_name,
                "shelf_life_date": shelf_life_date,
                "material_code": item.material_code,
                "internal_code": get_internal_code(item.name),
                "batch_no": batch_no
            })

    if not any_change:
        return

    issue_doc = None
    receipt_doc = None

    if issue_rows:
        issue_doc = create_stock_entry(item, warehouse, issue_rows, "Material Issue")

    if receipt_rows:
        receipt_doc = create_stock_entry(item, warehouse, receipt_rows, "Material Receipt")

    # Only print if successful
    if receipt_doc and label_table:
        print_purchasing_labels(json.dumps(label_table), is_legacy=True)

    return issue_doc, receipt_doc
