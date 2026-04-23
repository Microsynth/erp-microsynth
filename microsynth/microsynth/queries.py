# Copyright (c) 2026, Microsynth, libracore and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

@frappe.whitelist()
def purchase_items(doctype, txt, searchfield, start, page_len, filters):
    """
    This is an item query that filters based on item code, item name and supplier item numbers
    """
    supplier_condition = """ AND (`tabItem Supplier`.`supplier` IS NULL OR `tabItem Supplier`.`supplier` = "{supl}") """.format(supl=filters.get('supplier')) if filters.get('supplier') else ""
        
    data = frappe.db.sql(
        """SELECT `tabItem`.`name`, `tabItem`.`item_name`, `tabItem Supplier`.`supplier_part_no`
           FROM `tabItem`
           LEFT JOIN `tabItem Supplier` ON `tabItem Supplier`.`parent` = `tabItem`.`name`
           WHERE `tabItem`.`disabled` = 0
             AND `tabItem`.`is_purchase_item` = 1
             {supl_cond}
             AND (`tabItem`.`name` LIKE "%{s}%"
                  OR `tabItem`.`item_name` LIKE "%{s}%" 
                  OR `tabItem Supplier`.`supplier_part_no` LIKE "%{s}%");
        """.format(supl_cond=supplier_condition, s=txt))

    return data
    
