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


@frappe.whitelist()
def get_label_status(labels):
    """
    Check uniqueness of label: throw an error if multiple Labels with the barcode are found

    bench execute microsynth.microsynth.api.webshop.label.get_label_status --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY00043'}, {'item': '6030', 'barcode': 'MY00047'}]}"
    """
    # Check parameter
    if not labels or len(labels) == 0:
        return {'success': True, 'messages': []}
    try:
        messages_to_return = []
        for label in labels:
            if not 'item' in label or not label['item'] or not 'barcode' in label or not label['barcode']:
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'message': "Failed to get label status",
                    'internal_message': f"Label '{label['barcode']}' does not exist."  # Item and Barcode are both mandatory.
                })
                continue
            if not frappe.db.exists("Item", label['item']):
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'message': "Failed to get label status",
                    'internal_message': f"Label '{label['barcode']}' does not exist."  # f"The given Item '{label['item']}' does not exist in the ERP."
                })
                continue
            item_condition = f"AND `item` = {label['item']}"
            item_string = f" and Item Code {label['item']}"
            sql_query = f"""
                SELECT `item`,
                    `label_id` AS `barcode`,
                    `status`,
                    `registered`,
                    `contact`,
                    `registered_to`
                FROM `tabSequencing Label`
                WHERE `label_id` = '{label['barcode']}'
                    {item_condition}
                ;"""
            sequencing_labels = frappe.db.sql(sql_query, as_dict=True)
            if len(sequencing_labels) > 1:
                frappe.log_error(f"Found {len(sequencing_labels)} labels for the given barcode {label['barcode']}{item_string}.", "webshop.get_label_status")
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'internal_message': f"Found {len(sequencing_labels)} labels for the given barcode {label['barcode']}{item_string}.",
                    'message': f"Label '{label['barcode']}' is not valid. Please contact the Microsynth support."
                })
                continue
            elif len(sequencing_labels) == 0:
                #frappe.log_error(f"Found no label for the given barcode {label['barcode']}{item_string}.", "webshop.get_label_status")
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'internal_message': f"Label '{label['barcode']}' does not exist.",
                    'message': "Error getting label status"
                })
                continue
            else:
                messages_to_return.append({
                    'query': label,
                    'label': sequencing_labels[0],
                    'message': "OK",
                    'internal_message': "OK"
                })
        return {'success': True, 'messages': messages_to_return}
    except Exception as err:
        frappe.log_error(f"{labels=}\n{err}", "webshop.get_label_status")
        return {'success': False, 'messages': [{'query': None, 'label': None, 'message': err}]}
