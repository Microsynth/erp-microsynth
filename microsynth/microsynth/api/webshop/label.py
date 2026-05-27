import frappe
import traceback


@frappe.whitelist()
def get_unused_labels(contacts, items):
    """
    Return unused Sequencing Labels that are registered to a given contact.

    bench execute microsynth.microsynth.api.webshop.label.get_unused_labels --kwargs "{'contacts': ['215856', '237365'], 'items': ['6030', '6031', '3000', '3050'] }"
    """
    # Check parameters
    if not contacts or len(contacts) == 0:
        return {'success': False, 'message': "Failed to get unused labels", 'internal_message': "Please provide at least one Contact", 'labels': None}
    if not items or len(items) == 0:
        return {'success': False, 'message': "Failed to get unused labels", 'internal_message': "Please provide at least one Item", 'labels': None}
    for contact in contacts:
        if not frappe.db.exists("Contact", contact):
            return {'success': False, 'message': "Failed to get unused labels", 'internal_message': f"The given Contact '{contact}' does not exist in the ERP.", 'labels': None}
    for item in items:
        if not frappe.db.exists("Item", item):
            return {'success': False, 'message': "Failed to get unused labels", 'internal_message': f"The given Item '{item}' does not exist in the ERP.", 'labels': None}
    try:
        sql_query = """
            SELECT `item`,
                `label_id` AS `barcode`,
                `status`,
                `registered`,
                `contact`,
                `registered_to`
            FROM `tabSequencing Label`
            WHERE `status` = 'unused'
                AND `item` IN ({})
                AND `registered_to` IN ({})
            ;""".format(','.join(['%s'] * len(items)), ','.join(['%s'] * len(contacts)))
        labels = frappe.db.sql(sql_query, items + contacts, as_dict=True)
        return {'success': True, 'message': 'OK', 'internal_message': 'OK', 'labels': labels}
    except Exception as err:
        msg = f"Error fetching unused labels for contacts {contacts} and items {items}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_unused_labels")
        return {'success': False, 'message': "Failed to get unused labels", 'internal_message': msg, 'labels': None}
