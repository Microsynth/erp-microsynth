# Copyright (c) 2024, Microsynth and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 125 },
        {"label": _("Type"), "fieldname": "type", "fieldtype": "Data", "width": 70 },
        {"label": _("Oligos"), "fieldname": "oligo_count", "fieldtype": "Integer", "width": 55 },
        {"label": _("Envelope"), "fieldname": "envelope", "fieldtype": "Data", "width": 150 },
        #{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 300 },
        #{"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 65 },
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 90 },
        {"label": _("Shipping Label printed on"), "fieldname": "label_printed_on", "fieldtype": "Date", "width": 160 }
    ]


def get_data(filters):
    if not filters:
        return []
    inner_conditions = ""
    outer_conditions = ""
    if filters.get('date'):
        inner_conditions += f"AND DATE(`tabSales Order`.`label_printed_on`) = DATE('{filters.get('date')}')"
    if filters.get('tracking') and filters.get('tracking') == 'no Tracking':
        outer_conditions += f" AND `inner`.`items` LIKE '%1100%' "
    elif filters.get('tracking') and filters.get('tracking') == 'Tracking':
        outer_conditions += f" AND (`inner`.`items` LIKE '%1101%' OR `inner`.`items` LIKE '%1102%')"

    sql_query = f"""
        SELECT *
        FROM (
            SELECT
                `tabDelivery Note`.`name` AS `delivery_note`,
                `tabSales Order`.`name` AS `sales_order`,
                `tabDelivery Note`.`customer`,
                `tabDelivery Note`.`customer_name`,
                `tabDelivery Note`.`contact_person` AS `contact`,
                `tabDelivery Note`.`web_order_id`,
                (SELECT COUNT(`tabOligo`.`name`)
                    FROM `tabOligo Link`
                    LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
                    WHERE
                        `tabOligo Link`.`parent` = `tabDelivery Note`.`name`
                        AND `tabOligo Link`.`parenttype` = "Delivery Note"
                ) AS `oligo_count`,
                `tabSales Order`.`label_printed_on`,
                GROUP_CONCAT(`tabDelivery Note Item`.`item_code`) AS `items`
            FROM `tabDelivery Note`
            LEFT JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
            LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
            WHERE `tabDelivery Note`.`product_type` = 'Oligos'
                {inner_conditions}
            GROUP BY `tabDelivery Note`.`name`
            ) AS `inner`
        WHERE TRUE
            {outer_conditions}
        ;"""
    data = frappe.db.sql(sql_query, as_dict=True)

    standard_letters_b5 = 0
    large_letters = 0
    midi_letters_with_surcharge = 0
    own_label = 0

    for dn in data:
        items = set(dn['items'].split(','))
        plate_items = set(['0011', '0051', '0101', '0104', '0641'])
        if len(items.intersection(plate_items)) > 0:
            dn['type'] = 'Plate'
            if dn['oligo_count'] < 193:
                dn['envelope'] = 'Midi letter with surcharge'
                midi_letters_with_surcharge += 1
            else:
                dn['envelope'] = 'Parcel'
                own_label += 1
            continue
        else:
            dn['type'] = 'Tubes'
        if dn['oligo_count'] < 16:
            dn['envelope'] = 'Standard letter B5'
            standard_letters_b5 += 1
        elif dn['oligo_count'] < 61:
            dn['envelope'] = 'Large letter'
            large_letters += 1
        elif dn['oligo_count'] < 97:
            dn['envelope'] = 'Midi letter with surcharge'
            midi_letters_with_surcharge += 1
        else:
            dn['envelope'] = 'Parcel'
            own_label += 1

    summary_line = {
        'envelope': 'Summary:',
        'customer_name': f"Standard: {standard_letters_b5} | Large: {large_letters} | Midi: {midi_letters_with_surcharge} | Parcel: {own_label}"
    }
    data.append(summary_line)
    return data


def execute(filters):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def export_delivery_envelope_report(output_filepath, from_date, to_date, shipping_item_code):
    """
    Export Delivery Note envelope classification report as CSV.

    Args:
        output_filepath (str): Full path for the CSV file to be created.
        from_date (str): Start date in YYYY-MM-DD format.
        to_date (str): End date in YYYY-MM-DD format.
        shipping_item_code (str): Item code to filter shipping items (e.g. '1106').

    Returns:
        str: Path to the generated CSV file.

    bench execute microsynth.microsynth.report.oligo_envelope_sizes.oligo_envelope_sizes.export_delivery_envelope_report --kwargs "{'output_filepath': '/mnt/erp_share/JPe/2025-01-01_2025-09-30_delivery_envelope_report_Item_1106.csv', 'from_date': '2025-01-01', 'to_date': '2025-09-30', 'shipping_item_code': '1106'}"
    """
    import csv
    # --- SQL Query ---
    sql_query = """
        SELECT *
        FROM (
            SELECT
                `tabDelivery Note`.`name` AS `delivery_note`,
                `tabSales Order`.`name` AS `sales_order`,
                `tabDelivery Note`.`customer`,
                `tabDelivery Note`.`customer_name`,
                `tabDelivery Note`.`contact_person` AS `contact`,
                `tabDelivery Note`.`web_order_id`,
                (SELECT COUNT(`tabOligo`.`name`)
                    FROM `tabOligo Link`
                    LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
                    WHERE
                        `tabOligo Link`.`parent` = `tabDelivery Note`.`name`
                        AND `tabOligo Link`.`parenttype` = "Delivery Note"
                ) AS `oligo_count`,
                `tabSales Order`.`label_printed_on`,
                GROUP_CONCAT(`tabDelivery Note Item`.`item_code`) AS `items`
            FROM `tabDelivery Note`
            LEFT JOIN `tabDelivery Note Item`
                ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
            LEFT JOIN `tabSales Order`
                ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
            WHERE `tabDelivery Note`.`product_type` = 'Oligos'
              AND DATE(`tabSales Order`.`label_printed_on`) BETWEEN %(from_date)s AND %(to_date)s
            GROUP BY `tabDelivery Note`.`name`
        ) AS `inner`
        WHERE `inner`.`items` LIKE %(shipping_like)s
        ;
    """
    params = {
        "from_date": from_date,
        "to_date": to_date,
        "shipping_like": f"%{shipping_item_code}%"
    }
    data = frappe.db.sql(sql_query, params, as_dict=True)

    # --- Envelope Classification ---
    standard_letters_b5 = 0
    large_letters = 0
    midi_letters_with_surcharge = 0
    own_label = 0

    plate_items = {'0011', '0051', '0101', '0104', '0641'}

    for dn in data:
        items = set((dn.get('items') or '').split(','))

        if items & plate_items:
            dn['type'] = 'Plate'
            if dn['oligo_count'] < 193:
                dn['envelope'] = 'Midi letter with surcharge'
                midi_letters_with_surcharge += 1
            else:
                dn['envelope'] = 'Parcel'
                own_label += 1
        else:
            dn['type'] = 'Tubes'
            if dn['oligo_count'] < 16:
                dn['envelope'] = 'Standard letter B5'
                standard_letters_b5 += 1
            elif dn['oligo_count'] < 61:
                dn['envelope'] = 'Large letter'
                large_letters += 1
            elif dn['oligo_count'] < 97:
                dn['envelope'] = 'Midi letter with surcharge'
                midi_letters_with_surcharge += 1
            else:
                dn['envelope'] = 'Parcel'
                own_label += 1

    # --- Summary Row ---
    summary_line = {
        'delivery_note': '',
        'sales_order': '',
        'customer': '',
        'customer_name': 'SUMMARY',
        'contact': '',
        'web_order_id': '',
        'oligo_count': '',
        'label_printed_on': '',
        'items': '',
        'type': '',
        'envelope': (
            f"Standard: {standard_letters_b5} | "
            f"Large: {large_letters} | "
            f"Midi: {midi_letters_with_surcharge} | "
            f"Parcel: {own_label}"
        )
    }

    data.append(summary_line)

    # --- Write CSV File ---
    if not data:
        raise ValueError("No data found for given filters.")

    fieldnames = list(data[0].keys())

    with open(output_filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"Delivery envelope report exported to: {output_filepath}")
    return output_filepath
