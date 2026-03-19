# Copyright (c) 2026, Microsynth, libracore and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def purchase_items(doctype, txt, searchfield, start, page_len, filters):
    """
    This is an item query that filters based on item code, item name and supplier item numbers
    """
    return frappe.db.sql(
        """SELECT `tabItem`.`name`, `tabItem`.`item_name`, `tabItem Supplier`.`supplier_part_no`
           FROM `tabItem`
           LEFT JOIN `tabItem Supplier` ON `tabItem Supplier`.`parent` = `tabItem`.`name`
           WHERE `tabItem`.`disabled` = 0
             AND `tabItem`.`is_purchase_item` = 1
             AND (`tabItem`.`name` LIKE "%{s}%" 
                  OR `tabItem`.`item_name` LIKE "%{s}%" 
                  OR `tabItem Supplier`.`supplier_part_no` LIKE "%{s}%");
        """.format(s=txt))
