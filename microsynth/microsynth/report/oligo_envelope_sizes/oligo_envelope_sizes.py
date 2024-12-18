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
    conditions = ""
    
    if filters.get('date'):
        conditions += f"AND DATE(`tabSales Order`.`label_printed_on`) = DATE('{filters.get('date')}')"

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
                {conditions}
            GROUP BY `tabDelivery Note`.`name`
            ) AS `inner`
        WHERE `inner`.`items` LIKE '%1100%'
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
