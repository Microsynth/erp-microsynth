import frappe
from frappe.utils import flt
from microsynth.microsynth.labels import print_purchasing_labels

def get_purchasing_items(company="Microsynth AG"):
    """
    Returns purchasing items including default_warehouse for the given company.

    bench execute microsynth.microsynth.stock.get_purchasing_items --kwargs '{"company": "Microsynth AG"}'
    """
    # TODO: what is the purpose of this function? Where is it used?
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
    # TODO: Deprecate this function and move to api.stock.issue_material
    from microsynth.microsynth.api.stock import issue_material
    frappe.log_error(f"Called deprecated 'stock.issue_material' by {frappe.session.user}. Please change to 'api.stock.issue_material'.", "stock.issue_material")
    return issue_material(company, user, items)


def create_stock_entry(item, warehouse, rows, purpose):
    doc = frappe.new_doc("Stock Entry")
    doc.stock_entry_type = purpose
    doc.company = frappe.db.get_value("Warehouse", warehouse, "company")
    if not doc.company:
        frappe.throw(f"Warehouse {warehouse} does not have a company assigned.")

    for r in rows:
        doc.append("items", {
            "item_code": item.name,
            "qty": r["qty"],
            "uom": item.stock_uom,
            "conversion_factor": 1,
            "basic_rate": r.get("rate", 0),
            "allow_zero_valuation": 0,
            "s_warehouse": warehouse if purpose == "Material Issue" else None,
            "t_warehouse": warehouse if purpose == "Material Receipt" else None,
            "batch_no": r["batch_no"],
            "remarks": f"Stock correction for batch {r['batch_no']}"
        })
    doc.insert()
    doc.submit()
    return doc


def create_batch(item_code, batch_no, manufacturing_date=None, expiry_date=None):
    doc = frappe.new_doc("Batch")
    doc.item = item_code
    doc.batch_id = batch_no
    if manufacturing_date:
        doc.manufacturing_date = manufacturing_date
    if expiry_date:
        doc.expiry_date = expiry_date
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
    """

    batches = frappe.get_all(
        "Batch",
        filters={"item": item_code},
        fields=["name", "manufacturing_date", "expiry_date"],
        order_by="creation"
    )

    generic_batch = f"[NA]-{item_code}"

    batch_map = {b.name: b for b in batches}

    if generic_batch not in batch_map:
        batch_map[generic_batch] = frappe._dict({
            "name": generic_batch,
            "manufacturing_date": None,
            "expiry_date": None
        })

    result = []

    for batch_no, batch in batch_map.items():

        qty = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0)
            FROM `tabStock Ledger Entry`
            WHERE
                item_code = %s
                AND warehouse = %s
                AND batch_no = %s
                AND is_cancelled = 0
        """, (item_code, warehouse, batch_no))[0][0]

        result.append({
            "batch_no": batch_no,
            "manufacturing_date": batch.manufacturing_date,
            "expiry_date": batch.expiry_date,
            "current_qty": qty,
            "new_qty": qty
        })

    return result


@frappe.whitelist()
def correct_stock(item_code, warehouse, rows):
    """
    Correct stock levels for a given item and warehouse based on provided batch quantities.
    TODO: Make it work for non-batched Items as well.

    rows (List[Dict]):
    [
        {
            "batch_no": str,
            "current_qty": float,  # informational only (not trusted)
            "new_qty": float       # required, target quantity
        },
        ...
    ]

    bench execute microsynth.microsynth.stock.correct_stock --kwargs '{"item_code": "P002005", "warehouse": "Stores - BAL", "rows": [{"batch_no": "[NA]-P002005", "current_qty": 0, "new_qty": 10}]}'
    """
    # Check that User has Role "Stock User"
    if "Stock User" not in frappe.get_roles():
        frappe.throw("You do not have permission to perform this action.")

    rows = frappe.parse_json(rows)
    item = frappe.get_doc("Item", item_code)
    issue_rows = []
    receipt_rows = []
    label_table = []

    for row in rows:
        batch_no = row.get("batch_no")
        if not batch_no:
            frappe.throw("Batch number is required")

        result = frappe.db.sql("""
            SELECT IFNULL(SUM(`actual_qty`), 0) AS qty
            FROM `tabStock Ledger Entry`
            WHERE
                `item_code` = %(item_code)s
                AND `warehouse` = %(warehouse)s
                AND `batch_no` = %(batch_no)s
                AND `is_cancelled` = 0
        """, {
            "item_code": item_code,
            "warehouse": warehouse,
            "batch_no": batch_no
        }, as_dict=True)

        current_qty = result[0].qty if result else 0

        if row.get("new_qty") in [None, ""]:
            frappe.throw(f"New quantity missing for batch {batch_no}")
        try:
            new_qty = flt(row.get("new_qty"))
        except Exception:
            frappe.throw(f"Invalid quantity for batch {batch_no}")
        delta = new_qty - current_qty

        delta = flt(new_qty - current_qty, precision=2)  # Round to 2 decimals to avoid issues with very small differences

        if not delta:
            continue

        if not frappe.db.exists("Batch", batch_no):
            create_batch(item_code, batch_no, manufacturing_date=row.get("manufacturing_date"), expiry_date=row.get("expiry_date"))

        if delta < 0:
            if current_qty + delta < 0:
                frappe.throw(f"Negative stock not allowed for batch {batch_no}")

            issue_rows.append({
                "batch_no": batch_no,
                "qty": abs(delta)
            })

        else:
            rate = get_batch_rate(item_code, batch_no)  # TODO: Does it really work?

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

    if not issue_rows and not receipt_rows:
        return {
            "success": False,
            "changed_batches": 0,
            "message": "No stock changes detected."
        }

    issue_doc = None
    receipt_doc = None

    if issue_rows:
        issue_doc = create_stock_entry(item, warehouse, issue_rows, "Material Issue")

    if receipt_rows:
        receipt_doc = create_stock_entry(item, warehouse, receipt_rows, "Material Receipt")

    # Only print if successful
    if receipt_doc and label_table:
        print_purchasing_labels(frappe.as_json(label_table), is_legacy=True, use_brady=False)

    return {
        "success": True,
        "changed_batches": len(issue_rows) + len(receipt_rows),
        "issue_stock_entry": issue_doc.name if issue_doc else None,
        "receipt_stock_entry": receipt_doc.name if receipt_doc else None,
        "message": "Stock corrected successfully."
    }
