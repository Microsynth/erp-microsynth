import frappe

def find_purchasing_items(doctype, txt, seachfield, start, page_len, filters):
    parameters = {
        "txt": f"%{txt}%",
        "item_group": filters.get('item_group'),
        "supplier": f"%{filters.get('supplier')}%" if filters.get('supplier') else "%"
    }
    query = """
        SELECT DISTINCT `tabItem`.`item_code`, `tabItem`.`item_name`, `tabItem Supplier`.`supplier_part_no`
        FROM `tabItem`
        LEFT JOIN `tabItem Supplier` on `tabItem Supplier`.`parent` = `tabItem`.`name`
        WHERE (`tabItem`.`item_code` LIKE %(txt)s
        OR `tabItem`.`item_name` LIKE %(txt)s
        OR `tabItem Supplier`.`supplier_part_no` LIKE %(txt)s)
        AND `tabItem`.`item_group` = %(item_group)s
        AND `tabItem Supplier`.`supplier` like %(supplier)s; 
        """

    items = frappe.db.sql(query, parameters, as_dict=False)

    return items