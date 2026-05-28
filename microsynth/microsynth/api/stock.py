import json
import frappe


@frappe.whitelist(allow_guest=True)
def get_purchasing_items_with_internal_code():
    """
    Get a list of all enabled Purchasing Items with an internal code (item_code starting with P00).

    bench execute microsynth.microsynth.api.stock.get_purchasing_items_with_internal_code
    """
    # TODO: Item.name vs Item.item_code - which one should be returned? For now, we return both.
    items = frappe.db.sql("""
        SELECT
            `tabItem`.`item_code`,
            `tabItem`.`item_name`,
            RIGHT(`tabItem`.`item_code`, 4) AS `internal_code`,
            `tabItem`.`description`,
            `tabItem`.`material_code`,
            `tabItem`.`shelf_life_in_days`
        FROM `tabItem`
        WHERE `tabItem`.`disabled` = 0
            AND `tabItem`.`is_purchase_item` = 1
            AND `tabItem`.`item_group` = "Purchasing"
            AND `tabItem`.`item_code` LIKE "P00%"
        ORDER BY `internal_code` ASC;
    """, as_dict=True)

    return {
        'success': True,
        'message': 'OK',
        'items': items
    }


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

    bench execute microsynth.microsynth.api.stock.issue_material --kwargs '{"company": "Microsynth AG", "user": "firstname.lastname@microsynth.ch", "items": [{"item_code": "P007441", "qty": 2, "warehouse": "Stores - BAL", "batch_no": "HMBJ7023-HMBK0735"}]}'
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
