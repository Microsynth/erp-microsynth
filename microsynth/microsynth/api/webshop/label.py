import frappe
import traceback
import re

from microsynth.microsynth.seqblatt import process_label_status_change

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


def check_label_range(item, prefix, first_int, second_int):
    """
    Check if the given integers are both in the range of the Label Range of the given Item.
    """
    if not frappe.db.exists("Label Range", item):
        frappe.throw(f"There is no Label Range in the ERP for the given Item Code '{item}'.")
    label_range = frappe.get_doc("Label Range", item)
    if label_range.prefix and label_range.prefix != prefix:
        frappe.throw(f"The Label Range of the given Item Code '{item}' has prefix '{label_range.prefix}' "
                     f"but the given barcode_start_range and barcode_end_range have prefix '{prefix}'.")
    start_is_in_range = False
    end_is_in_range = False
    ranges = label_range.range.split(',')
    for r in ranges:
        parts = r.split('-')
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        if start <= first_int <= end:
            start_is_in_range = True
        if start <= second_int <= end:
            end_is_in_range = True
    if not (start_is_in_range and end_is_in_range):
        frappe.throw(f"Either {first_int} or {second_int} or both are out of range for the Label Range of the given Item '{item}'.")


def check_and_unfold_label_range(barcode_start_range, barcode_end_range, item):
    """
    Returns a list of all barcode labels from barcode_start_range to barcode_end_range (including both)

    bench execute microsynth.microsynth.webshop.check_and_unfold_label_range --kwargs "{'barcode_start_range': 'MY00001', 'barcode_end_range': 'MY00011', 'item': None}"
    """
    try:
        number_length = len(barcode_start_range)
        first_int = int(barcode_start_range)
        second_int = int(barcode_end_range)
        prefix = ""
    except Exception:
        # compile a regex
        cre = re.compile("([a-zA-Z]+)([0-9]+)")
        # match it to group text and numbers separately into a tuple
        first_split = cre.match(barcode_start_range).groups()
        second_split = cre.match(barcode_end_range).groups()
        # check if label prefixes are identical
        if first_split[0] != second_split[0]:
            frappe.throw(f"The given barcodes have different prefixes ({first_split[0]} != {second_split[0]})")
        prefix = first_split[0]
        number_length = len(first_split[1])
        first_int = int(first_split[1])
        second_int = int(second_split[1])
    if first_int > second_int:
        frappe.throw(f"The given barcode_start_range must be smaller or equal than the given barcode_end_range.")
    if item:
        check_label_range(item, prefix, first_int, second_int)
    barcodes = []
    for n in range(first_int, second_int + 1):
        barcodes.append(f"{prefix}{n:0{number_length}d}" if prefix else f"{n:0{number_length}d}")
    return barcodes


def check_and_get_sequencing_labels(registered_to, item, barcode_start_range, barcode_end_range):
    """
    Check the given parameters, check and unfold the given label range, return the Sequencing Labels as a list of dictionaries

    bench execute microsynth.microsynth.webshop.check_and_get_sequencing_labels --kwargs "{'registered_to': '215856', 'item': '3000', 'barcode_start_range': '96858440', 'barcode_end_range': '96858444'}"
    """
    if not (registered_to and barcode_start_range and barcode_end_range):
        return {'success': False, 'message': "Failed to get sequencing labels.", 'internal_message': "registered_to, barcode_start_range and barcode_end_range are mandatory parameters. Please provide all of them.", 'ranges': None}
    if item:
        if not frappe.db.exists("Item", item):
            return {'success': False, 'message': "Failed to get sequencing labels.", 'internal_message': f"The given Item '{item}' does not exist in the ERP.", 'ranges': None}
        item_condition = f"AND `item` = %s"
    else:
        item_condition = ""
    # check given label range
    barcodes = check_and_unfold_label_range(barcode_start_range, barcode_end_range, item)

    sql_query = f"""
        SELECT `name`,
            `item`,
            `label_id` AS `barcode`,
            `status`,
            `registered`,
            `contact`,
            `registered_to`
        FROM `tabSequencing Label`
        WHERE `label_id` IN ({','.join(['%s'] * len(barcodes))})
            {item_condition}
        ;"""
    return frappe.db.sql(sql_query, barcodes + ([item] if item else []), as_dict=True)


@frappe.whitelist()
def register_labels(registered_to, item, barcode_start_range, barcode_end_range):
    """
    Register the given label range to the given Contact after doing several checks.

    bench execute microsynth.microsynth.api.webshop.label.register_labels --kwargs "{'registered_to': '215856', 'item': '3000', 'barcode_start_range': '96858440', 'barcode_end_range': '96858444'}"
    """
    try:
        sequencing_labels = check_and_get_sequencing_labels(registered_to, item, barcode_start_range, barcode_end_range)
        registered_labels = []
        messages = ''
        for label in sequencing_labels:
            # check label
            if label['status'] != 'unused':
                message = 'Some labels were not registered because they were already used. '
                if not message in messages:
                    messages += message
                # do not change the affected Sequencing Label
                continue
            if label['registered'] or label['registered_to']:
                message = 'Some labels were not registered because they were already registered. '
                if not message in messages:
                    messages += message
                # do not change the affected Sequencing Label
                continue
            seq_label = frappe.get_doc("Sequencing Label", label['name'])
            # register label
            seq_label.registered = 1
            seq_label.registered_to = registered_to
            seq_label.save()
            label['registered_to'] = registered_to
            registered_labels.append(label)
        if len(registered_labels) > 0:
            return {'success': True, 'message': 'OK', 'internal_message': messages if messages else 'OK', 'ranges': partition_into_ranges(registered_labels)}
        else:
            return {'success': False, 'message': "Failed to register labels.", 'internal_message': 'Unable to register any labels. ' + messages, 'ranges': partition_into_ranges(registered_labels)}
    except Exception as err:
        msg = f"Error registering labels for registered_to {registered_to}, item {item}, barcode_start_range {barcode_start_range}, barcode_end_range {barcode_end_range}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.register_labels")
        return {'success': False, 'message': "Failed to register labels.", 'internal_message': msg, 'ranges': None}


@frappe.whitelist()
def unregister_labels(registered_to, item, barcode_start_range, barcode_end_range):
    """
    Unregister the given label range if it is registered to the given Contact

    bench execute microsynth.microsynth.api.webshop.label.unregister_labels --kwargs "{'registered_to': '215856', 'item': '3000', 'barcode_start_range': '96858440', 'barcode_end_range': '96858444'}"
    """
    try:
        sequencing_labels = check_and_get_sequencing_labels(registered_to, item, barcode_start_range, barcode_end_range)
        for label in sequencing_labels:
            # check label
            if label['registered_to'] != registered_to:
                return {'success': False, 'message': "Failed to unregister labels.", 'internal_message': f"Barcode {label['barcode']} is not registered to {registered_to}. Did not unregister any labels."}
        for label in sequencing_labels:
            # unregister label
            seq_label = frappe.get_doc("Sequencing Label", label['name'])
            seq_label.registered = 0
            seq_label.registered_to = None
            seq_label.save()
        return {'success': True, 'message': 'OK', 'internal_message': 'OK'}
    except Exception as err:
        msg = f"Error unregistering labels for registered_to {registered_to}, item {item}, barcode_start_range {barcode_start_range}, barcode_end_range {barcode_end_range}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.unregister_labels")
        return {'success': False, 'message': "Failed to unregister labels.", 'internal_message': msg}


@frappe.whitelist()
def set_label_submitted(labels):
    """
    Set the Status of the given Labels to submitted if they are unused and pass further tests.
    Try to submit as many labels as possible, return False if at least one given label could not be submitted

    bench execute microsynth.microsynth.api.webshop.label.set_label_submitted --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY004450', 'status': 'unused'}, {'item': '6030', 'barcode': 'MY004449', 'status': 'unused'}]}"
    """
    return process_label_status_change(
        labels=labels,
        target_status="submitted",
        required_current_statuses=["unused"]
    )


@frappe.whitelist()
def set_label_unused(labels):
    """
    Set the Status of the given Labels to unused if they are all submitted and pass further tests.

    bench execute microsynth.microsynth.api.webshop.label.set_label_unused --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY004450', 'status': 'submitted'}, {'item': '6030', 'barcode': 'MY004449', 'status': 'submitted'}]}"
    """
    return process_label_status_change(
        labels=labels,
        target_status="unused",
        required_current_statuses=["submitted"],
        check_not_used=True,
        stop_on_first_failure=True
    )
