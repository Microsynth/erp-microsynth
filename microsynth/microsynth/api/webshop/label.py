import frappe
import traceback
import re

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


@frappe.whitelist()
def get_label_ranges():
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Webshop-Label-API#get-label-ranges

    bench execute microsynth.microsynth.api.webshop.label.get_label_ranges
    """
    ranges_to_return = []
    try:  # range is also a SQL key word and needs therefore to be surrounded by backticks:
        label_ranges = frappe.get_all("Label Range", fields=['item_code', 'prefix', '`range`'])
        for label_range in label_ranges:
            ranges = label_range['range'].split(',')
            for r in ranges:
                parts = r.split('-')
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                ranges_to_return.append({
                    "item": label_range['item_code'],
                    "prefix": label_range['prefix'],
                    "barcode_start_range": start,
                    "barcode_end_range": end
                })
    except Exception as err:
        msg = f"Error fetching label ranges: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_label_ranges")
        return {'success': False, 'message': "Failed to get label ranges.", 'internal_message': msg, 'ranges': None}
    return {'success': True, 'message': 'OK', 'internal_message': 'OK', 'ranges': ranges_to_return}


def is_next_barcode(first_barcode, second_barcode):
    """
    Check if second_barcode follows immediatly after first_barcode
    """
    try:
        first_int = int(first_barcode)
        second_int = int(second_barcode)
        return first_int + 1 == second_int
    except Exception:
        try:
            # compile a regex
            cre = re.compile("([a-zA-Z]+)([0-9]+)")
            # match it to group text and numbers separately into a tuple
            first_split = cre.match(first_barcode).groups()
            second_split = cre.match(second_barcode).groups()
            # check if label prefixes are identical
            if first_split[0] == second_split[0]:
                return int(first_split[1]) + 1 == int(second_split[1])
            else:
                return False
        except Exception:
            return False


def partition_into_ranges(sequencing_labels):
    """
    Takes a list of dictionaries of labels sorted by barcode ascending and returns a list of dictionary of barcode ranges.
    """
    ranges = []
    if len(sequencing_labels) < 1:
        return ranges
    current_range_barcode = sequencing_labels[0]['barcode']
    barcode_range = {
        'registered_to': sequencing_labels[0]['registered_to'],
        'item': sequencing_labels[0]['item'],
        'barcode_start_range': current_range_barcode,
        'barcode_end_range': current_range_barcode
    }
    for i, label in enumerate(sequencing_labels):
        if i == 0:
            continue  # do not consider the first label a second time
        if label['registered_to'] != barcode_range['registered_to'] or label['item'] != barcode_range['item'] or not is_next_barcode(current_range_barcode, label['barcode']):
            # finish current barcode_range
            barcode_range['barcode_end_range'] = current_range_barcode
            ranges.append(barcode_range)
            # start a new barcode_range
            barcode_range = {
                'registered_to': label['registered_to'],
                'item': label['item'],
                'barcode_start_range': label['barcode'],
                'barcode_end_range': label['barcode']
            }
        current_range_barcode = label['barcode']
    # finish last barcode_range
    barcode_range['barcode_end_range'] = current_range_barcode
    if not barcode_range in ranges:
        # add last barcode_range
        ranges.append(barcode_range)
    return ranges


@frappe.whitelist()
def get_registered_label_ranges(contacts):
    """
    bench execute microsynth.microsynth.api.webshop.label.get_registered_label_ranges --kwargs "{'contacts': ['215856', '237365', 'invalid_contact']}"
    """
    # Check parameter
    if not contacts or len(contacts) == 0:
        return {'success': False, 'message': "Failed to get registered label ranges.", 'internal_message': "Please provide at least one Contact", 'ranges': None}
    try:
        sql_query = """
            SELECT `item`,
                `label_id` AS `barcode`,
                `registered_to`
            FROM `tabSequencing Label`
            WHERE `status` = 'unused'
                AND `registered_to` IN ({})
            ORDER BY `label_id` ASC
            ;""".format(','.join(['%s'] * len(contacts)))
        sequencing_labels = frappe.db.sql(sql_query, contacts, as_dict=True)
        if len(sequencing_labels) == 0:
            return {'success': True, 'message': 'OK', 'internal_message': 'No sequencing labels found.', 'ranges': []}
        ranges = partition_into_ranges(sequencing_labels)
        return {'success': True, 'message': 'OK', 'internal_message': 'OK', 'ranges': ranges}
    except Exception as err:
        msg = f"Error fetching registered label ranges for contacts {contacts}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_registered_label_ranges")
        return {'success': False, 'message': "Failed to get registered label ranges.", 'internal_message': msg, 'ranges': None}
